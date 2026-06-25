'use client';

function renderInline(text) {
  const parts = [];
  const pattern = /(\*\*[^*]+\*\*|\*[^*]+\*|`[^`]+`)/g;
  let last = 0;
  let match = pattern.exec(text);

  while (match) {
    if (match.index > last) {
      parts.push(<span key={`t-${last}`}>{text.slice(last, match.index)}</span>);
    }
    const token = match[0];
    if (token.startsWith('**')) {
      parts.push(
        <strong key={`b-${match.index}`} className="font-semibold text-gray-900">
          {token.slice(2, -2)}
        </strong>
      );
    } else if (token.startsWith('*')) {
      parts.push(
        <em key={`i-${match.index}`} className="italic text-gray-800">
          {token.slice(1, -1)}
        </em>
      );
    } else {
      parts.push(
        <code key={`c-${match.index}`} className="px-1 py-0.5 rounded bg-gray-200/80 text-[12px] font-mono text-gray-800">
          {token.slice(1, -1)}
        </code>
      );
    }
    last = match.index + token.length;
    match = pattern.exec(text);
  }

  if (last < text.length) {
    parts.push(<span key={`t-${last}`}>{text.slice(last)}</span>);
  }

  return parts.length ? parts : text;
}

function parseBlocks(content) {
  const lines = content.split('\n');
  const blocks = [];
  let paragraph = [];
  let listItems = [];
  let listOrdered = false;

  const flushParagraph = () => {
    if (paragraph.length) {
      blocks.push({ type: 'p', text: paragraph.join(' ') });
      paragraph = [];
    }
  };

  const flushList = () => {
    if (listItems.length) {
      blocks.push({ type: listOrdered ? 'ol' : 'ul', items: [...listItems] });
      listItems = [];
      listOrdered = false;
    }
  };

  for (const line of lines) {
    const trimmed = line.trim();
    const headingMatch = trimmed.match(/^(#{1,3})\s+(.+)$/);
    const bulletMatch = trimmed.match(/^[-*•]\s+(.+)$/);
    const numberedMatch = trimmed.match(/^\d+[.)]\s+(.+)$/);

    if (!trimmed) {
      flushList();
      flushParagraph();
      continue;
    }

    if (headingMatch) {
      flushList();
      flushParagraph();
      blocks.push({ type: 'h', level: headingMatch[1].length, text: headingMatch[2] });
      continue;
    }

    if (bulletMatch) {
      flushParagraph();
      if (listItems.length && listOrdered) flushList();
      listOrdered = false;
      listItems.push(bulletMatch[1]);
      continue;
    }

    if (numberedMatch) {
      flushParagraph();
      if (listItems.length && !listOrdered) flushList();
      listOrdered = true;
      listItems.push(numberedMatch[1]);
      continue;
    }

    flushList();
    paragraph.push(trimmed);
  }

  flushList();
  flushParagraph();
  return blocks;
}

const HEADING_CLASS = {
  1: 'text-base font-semibold text-gray-900 mt-1',
  2: 'text-sm font-semibold text-gray-900 mt-0.5',
  3: 'text-sm font-medium text-gray-800',
};

export default function ChatMarkdown({ content }) {
  if (!content) return null;

  const blocks = parseBlocks(content);

  return (
    <div className="space-y-3 text-sm leading-relaxed text-gray-800">
      {blocks.map((block, idx) => {
        if (block.type === 'h') {
          const Tag = block.level === 1 ? 'h4' : block.level === 2 ? 'h5' : 'h6';
          return (
            <Tag key={idx} className={HEADING_CLASS[block.level] || HEADING_CLASS[3]}>
              {renderInline(block.text)}
            </Tag>
          );
        }

        if (block.type === 'ul') {
          return (
            <ul key={idx} className="space-y-2 pl-0.5 my-1">
              {block.items.map((item, i) => (
                <li key={i} className="flex gap-2.5">
                  <span className="text-blue-500 mt-1 flex-shrink-0 text-[10px]">●</span>
                  <span className="flex-1">{renderInline(item)}</span>
                </li>
              ))}
            </ul>
          );
        }

        if (block.type === 'ol') {
          return (
            <ol key={idx} className="space-y-2 pl-0.5 my-1 list-none counter-reset-none">
              {block.items.map((item, i) => (
                <li key={i} className="flex gap-2.5">
                  <span className="text-gray-500 font-medium flex-shrink-0 w-4 text-right">{i + 1}.</span>
                  <span className="flex-1">{renderInline(item)}</span>
                </li>
              ))}
            </ol>
          );
        }

        return (
          <p key={idx} className="text-gray-800">
            {renderInline(block.text)}
          </p>
        );
      })}
    </div>
  );
}