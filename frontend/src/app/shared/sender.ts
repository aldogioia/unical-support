/** Parse the display name in a Gmail From header without inventing a person's name. */
export function senderInfo(raw: string): { name: string; address: string } {
  const value = raw.trim();
  const bracketed = value.match(/^(.*?)<([^<>]+)>/);
  if (bracketed) {
    const name = bracketed[1].trim().replace(/^"(.*)"$/, '$1').replace(/\\"/g, '"');
    return { name: name.includes('@') ? '' : name, address: bracketed[2].trim() };
  }
  const comment = value.match(/^([^\s<>]+@[^\s<>]+)\s+\(([^)]+)\)$/);
  if (comment) return { name: comment[2].trim(), address: comment[1] };
  return value.includes('@') ? { name: '', address: value } : { name: value, address: '' };
}
