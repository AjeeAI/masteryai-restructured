import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import remarkMath from 'remark-math';
import rehypeRaw from 'rehype-raw';
import rehypeKatex from 'rehype-katex';
import 'katex/dist/katex.min.css';

const LessonContent = ({ lessonData }) => {
  // Fix for Markdown Tables & Common Math spacing issues
  const formatContent = (text) => {
    if (!text) return "";
    return text
      .replace(/\|\s*\|/g, '|\n|') 
      .replace(/\\degree/g, '^\circ'); 
  };

  const renderContentBlock = (block, index) => {
    const type = block.type?.toLowerCase() || 'text';
    const markdownPlugins = [remarkGfm, remarkMath];
    const htmlPlugins = [rehypeRaw, rehypeKatex];

    const baseProse = "prose prose-slate max-w-none transition-all duration-200";
    const dynamicProse = "prose-headings:mt-8 prose-headings:mb-4 prose-headings:font-black prose-headings:text-slate-800 " +
                         "prose-p:leading-relaxed prose-p:mb-6 prose-p:text-slate-600 " +
                         "prose-li:my-2 prose-strong:text-indigo-700 " +
                         "prose-img:rounded-3xl prose-img:shadow-lg";

    // DEFENSIVE CONTENT EXTRACTION
    const mainContent = block.content || 
                       (block.value && typeof block.value === 'object' ? (block.value.content || block.value.prompt || block.value.question || "") : block.value) || 
                       "";
    
    const solution = block.solution || block.value?.solution || "";

    switch (type) {
      case 'image':
        if (!block.url) return null;
        return (
          <div key={index} className="mb-10 rounded-2xl md:rounded-3xl shadow-lg overflow-hidden border border-slate-200 bg-white">
            <img src={block.url} alt="Lesson visual aid" className="w-full h-auto object-cover" loading="lazy" />
            {mainContent && (
              <div className="bg-slate-50 p-4 text-center text-xs font-medium text-slate-500 border-t border-slate-200 uppercase tracking-wide">
                {mainContent}
              </div>
            )}
          </div>
        );

      case 'video':
        return (
          <div key={index} className="aspect-video bg-slate-900 rounded-2xl md:rounded-3xl mb-12 shadow-2xl overflow-hidden ring-1 ring-slate-200">
            {block.url ? <iframe src={block.url} className="w-full h-full" allowFullScreen title="Lesson Video"></iframe> : null}
          </div>
        );

      case 'example':
        return (
          <div key={index} className="bg-indigo-50/50 border-l-4 border-indigo-600 p-6 md:p-8 rounded-r-3xl mb-10 shadow-sm">
            <div className="flex items-center gap-2 mb-4">
               <span className="px-2 py-1 bg-indigo-600 text-[10px] font-black text-white uppercase tracking-tighter rounded">Example</span>
            </div>
            <div className={`${baseProse} prose-indigo prose-sm md:prose-base ${dynamicProse}`}>
              <ReactMarkdown remarkPlugins={markdownPlugins} rehypePlugins={htmlPlugins}>
                {formatContent(mainContent)}
              </ReactMarkdown>
            </div>
            {solution && (
              <div className="mt-6 p-5 bg-white rounded-2xl border border-indigo-100 shadow-sm">
                <span className="text-[10px] font-bold text-indigo-400 uppercase tracking-widest block mb-2">Detailed Solution</span>
                <div className={`${baseProse} prose-indigo prose-sm ${dynamicProse}`}>
                  <ReactMarkdown remarkPlugins={markdownPlugins} rehypePlugins={htmlPlugins}>
                    {formatContent(solution)}
                  </ReactMarkdown>
                </div>
              </div>
            )}
          </div>
        );

      case 'exercise':
        return (
          <div key={index} className="bg-emerald-50/50 border-l-4 border-emerald-600 p-6 md:p-8 rounded-r-3xl mb-10 shadow-sm">
            <div className="flex items-center gap-2 mb-4">
               <span className="px-2 py-1 bg-emerald-600 text-[10px] font-black text-white uppercase tracking-tighter rounded">Practice</span>
            </div>
            <div className={`${baseProse} prose-emerald prose-sm md:prose-base ${dynamicProse}`}>
              <ReactMarkdown remarkPlugins={markdownPlugins} rehypePlugins={htmlPlugins}>
                {formatContent(mainContent)}
              </ReactMarkdown>
            </div>
          </div>
        );

      default:
        const textBody = mainContent || block.note || "";
        return (
          <div key={index} className={`${baseProse} lg:prose-lg mb-12 dark:prose-invert ${dynamicProse}`}>
            <ReactMarkdown remarkPlugins={markdownPlugins} rehypePlugins={htmlPlugins}>
              {formatContent(textBody)}
            </ReactMarkdown>
          </div>
        );
    }
  };

  if (!lessonData) return <p className="text-center mt-20 text-slate-400">Select a topic to begin.</p>;

  return (
    <>
      <h1 className="text-3xl md:text-4xl font-black text-slate-900 mb-6 tracking-tight">{lessonData.title}</h1>
      <div className="space-y-2">
        {lessonData.content_blocks?.map((block, index) => renderContentBlock(block, index))}
      </div>
    </>
  );
};

export default LessonContent;