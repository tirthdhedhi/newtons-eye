import katex from "katex";

export interface TexProps {
  /** KaTeX source, e.g. "F = ma". */
  math: string;
  /** Render as a centered display equation instead of inline. */
  block?: boolean;
}

/** Renders LaTeX with KaTeX. Invalid input renders as red source text instead of throwing. */
export default function Tex({ math, block = false }: TexProps) {
  const html = katex.renderToString(math, { displayMode: block, throwOnError: false });
  const Tag = block ? "div" : "span";
  return <Tag dangerouslySetInnerHTML={{ __html: html }} />;
}
