/**
 * Markdown preprocessing and table repair utility.
 *
 * Fixes common LLM output anomalies:
 * 1. Double pipes (||) or (| |) used as row separators on a single line.
 * 2. Narrative text directly before a table row on the same line (e.g. "matches: | Goals | Frequency |").
 * 3. Narrative text directly after a table row on the same line (e.g. "| 3 | 1 | Draw a bar chart...").
 * 4. Missing blank lines before or after tables which prevents CommonMark / remark-gfm
 *    from interrupting active paragraphs.
 * 5. LaTeX degree shorthand (\degree -> ^\circ).
 */

export function repairMarkdownContent(rawText) {
  if (!rawText) return "";

  let text = String(rawText).replace(/\r\n/g, "\n");

  // Step 1: Separate concatenated table rows (|| or | |) into separate lines
  text = text.replace(/\|\s*\|/g, "|\n|");

  // Step 2: Line-by-line inspection to separate prose from table boundaries
  const lines = text.split("\n");
  const processedLines = [];

  for (let i = 0; i < lines.length; i++) {
    const rawLine = lines[i];
    const trimmed = rawLine.trim();

    if (!trimmed) {
      processedLines.push("");
      continue;
    }

    const firstPipe = trimmed.indexOf("|");
    const lastPipe = trimmed.lastIndexOf("|");

    // Case 1: Narrative text BEFORE a table row on the same line
    // e.g. "The table below shows ... : | Col 1 | Col 2 |"
    if (firstPipe > 0 && lastPipe === trimmed.length - 1) {
      const narrativeBefore = trimmed.slice(0, firstPipe).trim();
      const tableRow = trimmed.slice(firstPipe).trim();
      if (narrativeBefore) {
        processedLines.push(narrativeBefore);
        processedLines.push(""); // blank line before table
      }
      processedLines.push(tableRow);
      continue;
    }

    // Case 2: Table row followed by narrative text AFTER the last pipe
    // e.g. "| 3 | 1 | Draw a bar chart to represent this data."
    if (firstPipe === 0 && lastPipe > 0 && lastPipe < trimmed.length - 1) {
      const tableRow = trimmed.slice(0, lastPipe + 1).trim();
      const narrativeAfter = trimmed.slice(lastPipe + 1).trim();
      processedLines.push(tableRow);
      processedLines.push(""); // blank line after table
      if (narrativeAfter) {
        processedLines.push(narrativeAfter);
      }
      continue;
    }

    // Case 3: Line has BOTH narrative before AND narrative after a table row
    if (firstPipe > 0 && lastPipe > firstPipe && lastPipe < trimmed.length - 1) {
      const narrativeBefore = trimmed.slice(0, firstPipe).trim();
      const tableRow = trimmed.slice(firstPipe, lastPipe + 1).trim();
      const narrativeAfter = trimmed.slice(lastPipe + 1).trim();
      if (narrativeBefore) {
        processedLines.push(narrativeBefore);
        processedLines.push("");
      }
      processedLines.push(tableRow);
      processedLines.push("");
      if (narrativeAfter) {
        processedLines.push(narrativeAfter);
      }
      continue;
    }

    processedLines.push(trimmed);
  }

  // Step 3: Ensure double newlines between tables and paragraphs for CommonMark compliance
  const finalLines = [];
  for (let i = 0; i < processedLines.length; i++) {
    const curr = processedLines[i];
    const prev = finalLines[finalLines.length - 1];

    const prevIsRow = prev !== undefined && prev.startsWith("|") && prev.endsWith("|");
    const currIsRow = curr.startsWith("|") && curr.endsWith("|");

    // Transitioning from narrative text to a table row without a blank line
    if (prev !== undefined && prev !== "" && !prevIsRow && currIsRow) {
      finalLines.push("");
    }
    // Transitioning from a table row to narrative text without a blank line
    if (prev !== undefined && prev !== "" && prevIsRow && !currIsRow && curr !== "") {
      finalLines.push("");
    }

    finalLines.push(curr);
  }

  let result = finalLines.join("\n");

  // Step 4: Common LaTeX degree cleanups
  result = result.replace(/\\degree/g, "^\\circ");

  return result;
}

export default repairMarkdownContent;
