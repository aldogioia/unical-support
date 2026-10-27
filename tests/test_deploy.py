"""Deploy safety contracts; no network, Docker daemon or application DB required."""
import copy
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import shutil
import tempfile
import unittest
from unittest.mock import patch


def load_module(name, file):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).parents[1] / 'scripts' / file)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


local = load_module('deploy_local', 'deploy.py')
remote = load_module('deploy_remote', 'deploy_remote.py')


class DeployTests(unittest.TestCase):
    def test_payload_excludes_secrets_runtime_and_symlinks(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ['app/main.py', 'app/token.json', 'app/.env', 'app/secrets/password',
                         'frontend/node_modules/a.js', 'frontend/dist/index.html',
                         'frontend/src/main.ts', 'scripts/deploy.py']:
                file = root / name
                file.parent.mkdir(parents=True, exist_ok=True)
                file.write_text('example')
            (root / 'app/linked.py').symlink_to(root / 'app/token.json')
            actual = {str(relative) for _, relative in local.payload_files(root)}
            self.assertEqual(actual, {'app/main.py', 'frontend/src/main.ts', 'scripts/deploy.py'})

    def test_dry_run_does_not_connect(self):
        with patch.object(local.subprocess, 'run', side_effect=AssertionError('No network')), patch('builtins.print'):
            self.assertEqual(local.main(['--dry-run', '--migrate']), 0)

    def test_identity_is_applied_to_jump_without_disabling_host_verification(self):
        args = local.parser().parse_args(['--identity', '/keys/target', '--jump-identity', '/keys/jump'])
        command = local.ssh_args(args)
        self.assertIn('StrictHostKeyChecking=yes', command)
        proxy = next(x for x in command if x.startswith('ProxyCommand='))
        self.assertIn('IdentitiesOnly=yes', proxy)
        self.assertIn('/keys/jump', proxy)
        self.assertNotIn('StrictHostKeyChecking=no', proxy)

    def test_named_mount_refuses_bind_mount_database(self):
        with self.assertRaisesRegex(ValueError, 'volume Docker'):
            remote.named_mount({'Mounts': [{'Destination': remote.PG_PATH, 'Type': 'bind'}]}, remote.PG_PATH)

    def test_override_pins_existing_data_volumes_and_mounts_remote_oauth(self):
        inventory = {'volumes': {'postgres_data': 'old_pg', 'shared_uploads': 'old_files', 'celerybeat_data': 'old_beat'}, 'provider': 'gmail_api'}
        override = remote.override_config(inventory, Path('/releases/new'), Path('/private/runtime'))
        self.assertEqual(override['volumes']['postgres_data'], {'name': 'old_pg', 'external': True})
        self.assertEqual(override['volumes']['shared_uploads'], {'name': 'old_files', 'external': True})
        self.assertEqual(override['services']['worker']['volumes'][1]['source'], '/private/runtime/token.json')
        self.assertFalse(override['services']['worker']['volumes'][1]['bind']['create_host_path'])
        self.assertEqual(override['services']['frontend']['build']['context'], '/releases/new/frontend')

    def test_service_selection_ignores_oneoff_containers(self):
        def row(oneoff):
            return {'Config': {'Labels': {'com.docker.compose.project': 'existing', 'com.docker.compose.service': 'backend', 'com.docker.compose.oneoff': oneoff}}}
        self.assertEqual(remote.service_map([row('True'), row('False')], 'existing'), {'backend': row('False')})

    def test_release_heads_matches_real_repository(self):
        self.assertEqual(remote.release_heads(Path(__file__).parents[1]), ['a71d9c4e2f60'])

    @unittest.skipUnless(shutil.which('docker'), 'Docker Compose CLI opzionale, nessun daemon necessario')
    def test_real_compose_merge_pins_volumes_and_build_contexts(self):
        root = Path(__file__).parents[1]
        with tempfile.TemporaryDirectory() as directory:
            temporary = Path(directory)
            (temporary / 'empty.env').write_text('')
            inventory = {'volumes': {'postgres_data': 'existing_database', 'shared_uploads': 'existing_uploads', 'celerybeat_data': 'existing_scheduler'}, 'provider': 'gmail_api'}
            override = temporary / 'deploy.override.json'
            override.write_text(json.dumps(remote.override_config(inventory, root, temporary)))
            result = subprocess.run(['docker', 'compose', '-p', 'test-deploy', '--env-file', str(temporary / 'empty.env'),
                                     '-f', str(root / 'docker-compose.prod.yml'), '-f', str(override), 'config', '--format', 'json'],
                                    check=True, capture_output=True, text=True)
            rendered = json.loads(result.stdout)
            self.assertEqual(rendered['volumes']['postgres_data']['name'], 'existing_database')
            self.assertTrue(rendered['volumes']['postgres_data']['external'])
            self.assertEqual(rendered['services']['backend']['build']['context'], str(root))
            mounts = {m['target']: m for m in rendered['services']['worker']['volumes']}
            self.assertEqual(mounts['/app/uploads']['source'], 'shared_uploads')
            self.assertEqual(mounts['/app/token.json']['source'], str(temporary / 'token.json'))

    def test_remote_oauth_prefers_refreshed_worker_token_and_private_permissions(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runtime = root / 'runtime'
            runtime.mkdir()
            def copy(args, **kwargs):
                self.assertTrue(args[2].startswith('worker-id:/app/'))
                content = {'refresh_token': 'synthetic-refresh', 'token': 'synthetic-access'} if 'token.json' in args[2] else {'installed': {'client_id': 'synthetic'}}
                Path(args[3]).write_text(json.dumps(content))
                return subprocess.CompletedProcess(args, 0)
            with patch.object(remote.subprocess, 'run', side_effect=copy):
                remote.copy_oauth({'worker': 'worker-id', 'backend': 'backend-id'}, root, runtime)
            self.assertEqual(json.loads((runtime / 'token.json').read_text())['refresh_token'], 'synthetic-refresh')
            self.assertEqual(os.stat(runtime / 'token.json').st_mode & 0o777, 0o600)

    def test_lock_refuses_parallel_deploy(self):
        with tempfile.TemporaryDirectory() as directory:
            with remote.deployment_lock(Path(directory)):
                with self.assertRaisesRegex(ValueError, 'deploy è già in corso'):
                    with remote.deployment_lock(Path(directory)):
                        self.fail('Acquired duplicate lock')

    def workflow(self, *, migrate=True, current=None, backup_failure=False):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        release = root / '.deploy/releases/new'
        release.mkdir(parents=True)
        ids = {name: name + '-id' for name in ['db', 'redis', *remote.APP_SERVICES]}
        inventory = {'project': 'existing', 'remote_dir': str(root), 'provider': 'smtp', 'overlays': [],
                     'volumes': {'postgres_data': 'original_pg', 'shared_uploads': 'original_uploads', 'celerybeat_data': 'beat_data'}, 'containers': ids}
        config = {**copy.deepcopy(inventory), 'release': str(release), 'build': 'all', 'no_cache': False, 'migrate': migrate}
        calls = []
        def execute(*args, **kwargs):
            calls.append(list(args))
            return subprocess.CompletedProcess(args, 0)
        def inspect(identifier):
            return {'Image': 'sha256:previous', 'State': {'Running': True},
                    'Mounts': [{'Destination': remote.PG_PATH, 'Type': 'volume', 'Name': 'original_pg'}]}
        def output(*args):
            calls.append(list(args))
            if 'get_heads()' in args[-1]:
                return '["new_head"]'
            return json.dumps(['old_head'] if current is None else current)
        def backup(container, path):
            calls.append(['BACKUP', container])
            if backup_failure:
                raise ValueError('backup failed')
            path.write_bytes(b'PGDMP')
        patches = [patch.object(remote, 'discover', return_value=inventory),
                   patch.object(remote, 'inspect_container', side_effect=inspect),
                   patch.object(remote, 'run', side_effect=execute),
                   patch.object(remote, 'output', side_effect=output),
                   patch.object(remote, 'release_heads', return_value=['new_head']),
                   patch.object(remote, 'database_backup', side_effect=backup),
                   patch.object(remote, 'wait_ready'), patch.object(remote, 'containers', return_value=[]),
                   patch.object(remote, 'service_map', return_value={'worker': {'Config': {'Hostname': 'worker-new'}}}),
                   patch.object(remote.subprocess, 'run', side_effect=lambda args, **kwargs: execute(*args, **kwargs))]
        return config, calls, patches

    def invoke(self, config, patches):
        from contextlib import ExitStack
        with ExitStack() as stack:
            for item in patches:
                stack.enter_context(item)
            remote.deploy(config)

    def test_migration_follows_verified_backup_and_never_recreates_database(self):
        config, calls, patches = self.workflow()
        self.invoke(config, patches)
        backup = next(i for i, c in enumerate(calls) if c[0] == 'BACKUP')
        migration = next(i for i, c in enumerate(calls) if c[-3:] == ['alembic', 'upgrade', 'head'])
        self.assertLess(backup, migration)
        for command in calls:
            if 'up' in command or 'stop' in command:
                self.assertNotIn('db', command)
                self.assertNotIn('redis', command)
            self.assertNotIn('down', command)
            self.assertNotIn('stamp', command)
        manifest = json.loads((Path(config['release']) / 'manifest.json').read_text())
        self.assertTrue(manifest['completed'])
        self.assertEqual(manifest['volumes']['postgres_data'], 'original_pg')

    def test_missing_migrate_flag_refuses_before_stopping_services(self):
        config, calls, patches = self.workflow(migrate=False)
        with self.assertRaisesRegex(ValueError, '--migrate'):
            self.invoke(config, patches)
        self.assertFalse(any('stop' in command for command in calls))

    def test_failed_backup_prevents_schema_updates_and_container_rollout(self):
        config, calls, patches = self.workflow(backup_failure=True)
        with self.assertRaisesRegex(ValueError, 'backup failed'):
            self.invoke(config, patches)
        self.assertFalse(any('upgrade' in command or 'up' in command for command in calls))

    def test_unchanged_schema_without_migration_still_has_backup(self):
        config, calls, patches = self.workflow(migrate=False, current=['new_head'])
        self.invoke(config, patches)
        self.assertTrue(any(command[0] == 'BACKUP' for command in calls))
        self.assertFalse(any('upgrade' in command for command in calls))


if __name__ == '__main__':
    unittest.main()
