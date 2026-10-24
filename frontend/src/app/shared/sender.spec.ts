import { senderInfo } from './sender';

describe('Sender display', () => {
  it('keeps a display name separate from the address', () => {
    expect(senderInfo('Aldo Gioia <aldo@example.org>')).toEqual({ name: 'Aldo Gioia', address: 'aldo@example.org' });
    expect(senderInfo('"Rossi, Giulia" <giulia@example.org>')).toEqual({ name: 'Rossi, Giulia', address: 'giulia@example.org' });
    expect(senderInfo('giulia@example.org (Giulia Rossi)')).toEqual({ name: 'Giulia Rossi', address: 'giulia@example.org' });
  });
  it('does not invent a person name from a bare email or a missing sender', () => {
    expect(senderInfo('student@example.org')).toEqual({ name: '', address: 'student@example.org' });
    expect(senderInfo('<student@example.org>')).toEqual({ name: '', address: 'student@example.org' });
    expect(senderInfo('  ')).toEqual({ name: '', address: '' });
  });
});
