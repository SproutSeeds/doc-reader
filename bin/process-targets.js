export function isWebProcessForPort(command, port) {
  if (!/(?:^|\s)-m\s+doc_reader\.webapp(?:\s|$)/.test(command)) return false;
  const match = command.match(/(?:^|\s)--port(?:=|\s+)(\d+)(?=\s|$)/);
  if (/(?:^|\s)--port(?:=|\s)/.test(command) && !match) return false;
  return Number(match?.[1] || 8766) === Number(port);
}
