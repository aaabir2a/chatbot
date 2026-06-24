// Minimal, safe Markdown -> HTML for chat bubbles.
// Security: ALL text is HTML-escaped first, so model output can never inject
// markup. Only our own whitelisted tags (strong/em/code/a/ul/ol/li/br) are
// added afterwards, and links are restricted to http(s).

function escapeHtml(s: string): string {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function inline(s: string): string {
  // `code`
  s = s.replace(/`([^`]+)`/g, "<code>$1</code>");
  // **bold** / __bold__
  s = s.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
  s = s.replace(/__([^_]+)__/g, "<strong>$1</strong>");
  // *italic* (single star, not part of a bullet — bold already consumed)
  s = s.replace(/(^|[^*])\*([^*\n]+)\*/g, "$1<em>$2</em>");
  // [text](https://url)
  s = s.replace(
    /\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g,
    '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>',
  );
  return s;
}

export function renderMarkdown(src: string): string {
  const lines = escapeHtml(src).split("\n");
  let html = "";
  let inUl = false;
  let inOl = false;
  const closeLists = () => {
    if (inUl) {
      html += "</ul>";
      inUl = false;
    }
    if (inOl) {
      html += "</ol>";
      inOl = false;
    }
  };

  for (const raw of lines) {
    const line = raw;
    const heading = line.match(/^\s*#{1,6}\s+(.*)$/);
    const ul = line.match(/^\s*[-*]\s+(.*)$/);
    const ol = line.match(/^\s*\d+\.\s+(.*)$/);

    if (heading) {
      closeLists();
      html += `<strong>${inline(heading[1])}</strong><br>`;
    } else if (ul) {
      if (inOl) {
        html += "</ol>";
        inOl = false;
      }
      if (!inUl) {
        html += "<ul>";
        inUl = true;
      }
      html += `<li>${inline(ul[1])}</li>`;
    } else if (ol) {
      if (inUl) {
        html += "</ul>";
        inUl = false;
      }
      if (!inOl) {
        html += "<ol>";
        inOl = true;
      }
      html += `<li>${inline(ol[1])}</li>`;
    } else if (line.trim() === "") {
      closeLists();
      html += "<br>";
    } else {
      closeLists();
      html += `${inline(line)}<br>`;
    }
  }
  closeLists();
  // Trim a single trailing <br> for tidiness.
  return html.replace(/(<br>)+$/, "");
}
