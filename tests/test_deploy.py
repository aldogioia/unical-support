"""Deploy safety contracts; no network, Docker daemon or application DB required."""
import copy
import importlib.util
import io
import json
import os
import shlex
from pathlib import Path
import subprocess
import shutil
import tempfile
import tarfile
import unittest
from unittest.mock import patch


def load_module(name, file):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).parents[1] / 'scripts' / file)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


local = load_module('deploy_local', 'deploy.py')
remote = load_module('deploy_remote', 'deploy_remote.py')


def oauth_archive(filename, content):
    stream = io.BytesIO()
    value = json.dumps(content).encode()
    with tarfile.open(fileobj=stream, mode='w') as archive:
        member = tarfile.TarInfo(filename)
        member.size = len(value)
        archive.addfile(member, io.BytesIO(value))
    return stream.getvalue()


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

    def test_password_mode_enables_both_hops_and_allows_time_for_two_prompts(self):
        args = local.parser().parse_args(['--interactive-ssh'])
        command = local.ssh_args(args)
        proxy = next(x for x in command if x.startswith('ProxyCommand='))
        self.assertIn('BatchMode=no', command)
        self.assertIn('BatchMode=no', proxy)
        self.assertIn('ConnectTimeout=180', command)
        self.assertIn('ConnectTimeout=180', proxy)
        self.assertIn('StrictHostKeyChecking=yes', command)
        self.assertIn('StrictHostKeyChecking=yes', proxy)

    def test_unattended_mode_does_not_prompt_on_either_host(self):
        command = local.ssh_args(local.parser().parse_args([]))
        proxy = next(x for x in command if x.startswith('ProxyCommand='))
        self.assertIn('BatchMode=yes', command)
        self.assertIn('BatchMode=yes', proxy)

    def test_check_authenticates_before_piping_and_closes_its_private_connection(self):
        calls = []
        def execute(command, **kwargs):
            calls.append((command, kwargs))
            return subprocess.CompletedProcess(command, 0, stdout=b'{"project":"existing"}')
        with patch.object(local.subprocess, 'run', side_effect=execute), patch('builtins.print'):
            self.assertEqual(local.main(['--interactive-ssh', '--check']), 0)
        self.assertEqual(len(calls), 3)
        master, inspection, cleanup = calls
        self.assertIn('-M', master[0])
        self.assertIn('-N', master[0])
        self.assertEqual(master[1]['stdin'], subprocess.DEVNULL)
        self.assertNotIn('input', master[1])
        self.assertIn(b'def discover', inspection[1]['input'])
        self.assertIn('-O', cleanup[0])
        self.assertIn('exit', cleanup[0])
        sockets = {next(x for x in command if x.startswith('ControlPath=')) for command, _ in calls}
        self.assertEqual(len(sockets), 1)
        self.assertFalse(Path(next(iter(sockets)).split('=', 1)[1]).parent.exists())

    def test_remote_failure_closes_private_connection_without_hiding_error(self):
        calls = []
        failure = subprocess.CalledProcessError(255, ['ssh'])
        def execute(command, **kwargs):
            calls.append(command)
            if len(calls) == 2:
                raise failure
            return subprocess.CompletedProcess(command, 0)
        args = local.parser().parse_args(['--interactive-ssh'])
        with patch.object(local.subprocess, 'run', side_effect=execute), patch('builtins.print'):
            with self.assertRaises(subprocess.CalledProcessError) as caught:
                with local.ssh_connection(args) as command:
                    local.subprocess.run(command + ['false'], check=True)
        self.assertIs(caught.exception, failure)
        self.assertEqual(len(calls), 3)
        self.assertIn('-O', calls[-1])

    def test_deploy_upload_and_remote_execution_reuse_authenticated_master(self):
        calls = []
        inventory = {'project': 'existing', 'remote_dir': '/home/operatore/unical_support'}
        def execute(command, **kwargs):
            calls.append((command, kwargs))
            return subprocess.CompletedProcess(command, 0, stdout=json.dumps(inventory).encode())
        with (patch.object(local.subprocess, 'run', side_effect=execute), patch('builtins.print'),
              patch.object(local, 'payload_files', return_value=[])):
            self.assertEqual(local.main(['--interactive-ssh', '--build', 'all', '--migrate']), 0)
        self.assertEqual(len(calls), 5)
        self.assertIn('tar -xzf', calls[2][0][-1])
        self.assertIn('stdin', calls[2][1])
        self.assertIn('deploy_remote.py deploy', calls[3][0][-1])
        sockets = {next(x for x in command if x.startswith('ControlPath=')) for command, _ in calls}
        self.assertEqual(len(sockets), 1)

    def test_sudo_inspection_uses_terminal_and_separate_private_json_file(self):
        calls = []
        def execute(command, **kwargs):
            calls.append((command, kwargs))
            content = '/tmp/unical-deploy.test123\n' if kwargs.get('text') else b'{"project":"existing"}'
            return subprocess.CompletedProcess(command, 0, stdout=content)
        with patch.object(local.subprocess, 'run', side_effect=execute):
            inventory = local.inspect_with_privileges({'sudo': True}, ['ssh', '--', 'UnicalSupport'], b'# helper')
        self.assertEqual(inventory['project'], 'existing')
        self.assertEqual(len(calls), 5)
        self.assertEqual(calls[1][1]['input'], b'# helper')
        self.assertIn('-tt', calls[2][0])
        self.assertNotIn('stdout', calls[2][1])
        self.assertNotIn('input', calls[2][1])
        self.assertEqual(calls[3][1]['stdout'], subprocess.PIPE)
        self.assertIn('unlink', calls[4][0][-1])

    def test_sudo_deploy_preserves_unprivileged_upload_and_interactive_execution(self):
        calls = []
        inventory = {'project': 'existing', 'remote_dir': '/home/operatore/unical_support'}
        def execute(command, **kwargs):
            calls.append((command, kwargs))
            return subprocess.CompletedProcess(command, 0)
        with (patch.object(local.subprocess, 'run', side_effect=execute), patch('builtins.print'),
              patch.object(local, 'inspect_with_privileges', return_value=inventory) as inspect,
              patch.object(local, 'payload_files', return_value=[])):
            self.assertEqual(local.main(['--interactive-ssh', '--sudo', '--build', 'all']), 0)
        self.assertTrue(inspect.call_args.args[0]['sudo'])
        self.assertNotIn('-tt', calls[1][0])
        self.assertIn('tar -xzf', calls[1][0][-1])
        self.assertIn('-tt', calls[2][0])
        self.assertIn('deploy_remote.py deploy', calls[2][0][-1])

    def test_sudo_only_elevates_docker_and_preserves_io(self):
        with patch.object(remote, 'DOCKER_SUDO', True), patch.object(remote.subprocess, 'run') as run:
            remote.execute(['docker', 'exec', 'db', 'pg_dump'], stdout='binary-backup')
            self.assertEqual(run.call_args_list[0].args[0], ['sudo', '-v'])
            self.assertEqual(run.call_args_list[1].args[0], ['sudo', '-n', 'docker', 'exec', 'db', 'pg_dump'])
            self.assertEqual(run.call_args_list[1].kwargs['stdout'], 'binary-backup')
            run.reset_mock()
            remote.execute(['python3', '--version'])
            run.assert_called_once_with(['python3', '--version'])

    def test_sudo_dump_and_restore_validation_keep_password_out_of_binary_stdin(self):
        calls = []
        def execute(command, **kwargs):
            calls.append(command)
            if command == ['sudo', '-v']:
                self.assertNotIn('stdin', kwargs)
                self.assertNotIn('input', kwargs)
            elif command[-1] == '--list':
                self.assertEqual(kwargs['stdin'].read(), b'PGDMP-synthetic')
            else:
                kwargs['stdout'].write(b'PGDMP-synthetic')
            return subprocess.CompletedProcess(command, 0)
        with tempfile.TemporaryDirectory() as directory:
            backup = Path(directory) / 'backup.dump'
            with patch.object(remote, 'DOCKER_SUDO', True), patch.object(remote.subprocess, 'run', side_effect=execute):
                remote.database_backup('existing-db', backup)
            self.assertEqual(backup.stat().st_mode & 0o777, 0o600)
            self.assertEqual(backup.stat().st_uid, os.getuid())
        self.assertEqual(calls.count(['sudo', '-v']), 2)

    def test_sudo_prefix_is_saved_in_compose_command_without_double_wrapping(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(remote, 'DOCKER_SUDO', True):
            inventory = {'remote_dir': directory, 'project': 'existing', 'provider': 'gmail_api', 'overlays': []}
            command = remote.compose_command({}, inventory, Path(directory), Path(directory) / 'override.json')
            self.assertEqual(command[:3], ['sudo', '-n', 'docker'])
            self.assertEqual(remote.docker_command(command), command)

    def test_su_and_sudo_are_mutually_exclusive(self):
        with patch('sys.stderr'), self.assertRaises(SystemExit) as error:
            local.parser().parse_args(['--sudo', '--su'])
        self.assertEqual(error.exception.code, 2)

    def test_su_wraps_helper_as_single_safely_quoted_command(self):
        helper = Path("/tmp/project's release/helper.py")
        command = local.helper_command(helper, 'inspect', {'su': True})
        outer = shlex.split(command)
        self.assertEqual(outer[:4], ['su', '--login', 'root', '--command'])
        inner = shlex.split(outer[4])
        self.assertEqual(inner[:4], ['exec', 'python3', str(helper), 'inspect'])
        self.assertNotIn('sudo', inner)

    def test_su_deploy_reads_original_owner_and_elevates_execution_without_elevating_upload(self):
        calls = []
        inventory = {'project': 'existing', 'remote_dir': '/home/operatore/unical_support'}
        owner = {'uid': 1000, 'gid': 1000, 'groups': [1000, 1001]}
        def execute(command, **kwargs):
            calls.append((command, kwargs))
            return subprocess.CompletedProcess(command, 0)
        with (patch.object(local.subprocess, 'run', side_effect=execute), patch('builtins.print'),
              patch.object(local, 'remote_file_owner', return_value=owner) as owner_query,
              patch.object(local, 'inspect_with_privileges', return_value=inventory) as inspect,
              patch.object(local, 'payload_files', return_value=[])):
            self.assertEqual(local.main(['--interactive-ssh', '--su', '--build', 'all']), 0)
        owner_query.assert_called_once()
        self.assertEqual(inspect.call_args.args[0]['file_owner'], owner)
        self.assertTrue(inspect.call_args.args[0]['su'])
        self.assertFalse(inspect.call_args.args[0]['sudo'])
        self.assertNotIn('-tt', calls[1][0])
        self.assertIn('tar -xzf', calls[1][0][-1])
        self.assertIn('-tt', calls[2][0])
        self.assertEqual(shlex.split(calls[2][0][-1])[:4], ['su', '--login', 'root', '--command'])

    def test_su_inspection_uses_terminal_and_keeps_inventory_readable_by_original_user(self):
        calls = []
        def execute(command, **kwargs):
            calls.append((command, kwargs))
            content = '/tmp/unical-deploy.test123\n' if kwargs.get('text') else b'{"project":"existing"}'
            return subprocess.CompletedProcess(command, 0, stdout=content)
        config = {'su': True, 'file_owner': {'uid': 1000, 'gid': 1000, 'groups': [1000]}}
        with patch.object(local.subprocess, 'run', side_effect=execute):
            result = local.inspect_with_privileges(config, ['ssh', '--', 'UnicalSupport'], b'# helper')
        self.assertEqual(result['project'], 'existing')
        self.assertIn('-tt', calls[2][0])
        self.assertEqual(shlex.split(calls[2][0][-1])[:4], ['su', '--login', 'root', '--command'])
        self.assertNotIn('stdout', calls[2][1])
        self.assertEqual(calls[3][0][-1], 'cat /tmp/unical-deploy.test123/inventory.json')

    def test_su_parent_restores_file_identity_before_any_docker_execution(self):
        events = []
        owner = {'uid': 1000, 'gid': 1001, 'groups': [1001, 1002]}
        with (patch.object(remote, 'DOCKER_SU', False),
              patch.object(remote.os, 'getuid', return_value=0),
              patch.object(remote.os, 'geteuid', return_value=0),
              patch.object(remote.os, 'setgroups', side_effect=lambda value: events.append(('groups', value))),
              patch.object(remote.os, 'setegid', side_effect=lambda value: events.append(('gid', value))),
              patch.object(remote.os, 'seteuid', side_effect=lambda value: events.append(('uid', value)))):
            remote.configure_su({'su': True, 'file_owner': owner})
            self.assertTrue(remote.DOCKER_SU)
        self.assertEqual(events, [('groups', [1001, 1002]), ('gid', 1001), ('uid', 1000)])

    def test_su_refuses_missing_root_authentication_and_missing_original_identity(self):
        with patch.object(remote.os, 'getuid', return_value=1000):
            with self.assertRaisesRegex(ValueError, 'su root'):
                remote.configure_su({'su': True})
        with patch.object(remote.os, 'getuid', return_value=0), patch.object(remote.os, 'geteuid', return_value=0):
            with self.assertRaisesRegex(ValueError, 'Identità originale'):
                remote.configure_su({'su': True})

    def test_su_docker_children_get_root_without_sudo_or_authentication_in_binary_streams(self):
        with (patch.object(remote, 'DOCKER_SU', True), patch.object(remote, 'DOCKER_SUDO', False),
              patch.object(remote.subprocess, 'run') as run,
              patch.object(remote, 'docker_root_child') as regain_root):
            remote.execute(['docker', 'exec', '-i', 'db', 'pg_restore', '--list'], stdin='binary-backup')
            run.assert_called_once_with(['docker', 'exec', '-i', 'db', 'pg_restore', '--list'],
                                        stdin='binary-backup', preexec_fn=regain_root)
            regain_root.assert_not_called()
            run.reset_mock()
            remote.execute(['python3', '--version'])
            run.assert_called_once_with(['python3', '--version'])

    def test_root_credentials_are_restored_only_in_docker_child(self):
        events = []
        with (patch.object(remote.os, 'seteuid', side_effect=lambda v: events.append(('euid', v))),
              patch.object(remote.os, 'setgroups', side_effect=lambda v: events.append(('groups', v))),
              patch.object(remote.os, 'setgid', side_effect=lambda v: events.append(('gid', v))),
              patch.object(remote.os, 'setuid', side_effect=lambda v: events.append(('uid', v)))):
            remote.docker_root_child()
        self.assertEqual(events, [('euid', 0), ('groups', [0]), ('gid', 0), ('uid', 0)])

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
                self.assertEqual(args[3], '-')
                return subprocess.CompletedProcess(args, 0, stdout=oauth_archive(Path(args[2]).name, content))
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
