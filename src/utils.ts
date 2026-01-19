import { marked } from 'marked';
import DOMPurify from 'dompurify';

// Configure marked options
marked.setOptions({
  breaks: true, // Convert \n to <br>
  gfm: true, // GitHub Flavored Markdown
});

// Render markdown text safely
export function renderMarkdown(text: string): { __html: string } {
  if (!text) return { __html: '' };
  
  const rawHtml = marked.parse(text) as string;
  let cleanHtml = DOMPurify.sanitize(rawHtml, {
    ALLOWED_TAGS: ['p', 'br', 'strong', 'em', 'u', 's', 'code', 'pre', 'a', 'ul', 'ol', 'li', 'blockquote', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'hr'],
    ALLOWED_ATTR: ['href', 'target', 'rel'],
    ALLOWED_URI_REGEXP: /^(?:(?:(?:f|ht)tps?|mailto|tel|callto|sms|cid|xmpp|vscode|file):|[^a-z]|[a-z+.\-]+(?:[^a-z+.\-:]|$))/i
  });
  
  // Remove <a> tags without href attribute (convert to plain text)
  cleanHtml = cleanHtml.replace(/<a>([^<]*)<\/a>/g, '$1');
  
  // Ensure all links open in new tab
  cleanHtml = cleanHtml.replace(/<a href=/g, '<a target="_blank" rel="noopener noreferrer" href=');
  
  return { __html: cleanHtml };
}

export interface Task {
  id: number;
  task: string;
  done: boolean;
  parent_id: number | null;
  position: number;
  comments: string;
  is_current: boolean;
  board_x: number;
  board_y: number;
  board_width: number;
  board_height: number;
  children_layout: 'vertical' | 'horizontal';
  children_comment_display: 'full' | 'compact' | 'none';
  children: Task[];
}
