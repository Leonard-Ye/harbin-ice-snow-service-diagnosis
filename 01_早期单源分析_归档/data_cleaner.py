import pandas as pd
import re
import os
import emoji

def clean_text(text):
    if pd.isna(text):
        return ""
    text = str(text)
    # Remove URLs
    text = re.sub(r'http[s]?://\S+', '', text)
    # Remove HTML tags
    text = re.sub(r'<.*?>', '', text)
    # Remove platform emojis in brackets e.g., [笑哭], 【捂脸】
    text = re.sub(r'\[.*?\]', '', text)
    text = re.sub(r'【.*?】', '', text)
    # Remove standard unicode emojis
    text = emoji.replace_emoji(text, replace='')
    # Remove excessive newlines and spaces
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def main():
    print("开始数据清洗...")
    notes_path = 'final_notes.csv'
    comments_path = 'final_comments.csv'
    
    notes_df = pd.DataFrame()
    if os.path.exists(notes_path):
        try:
            notes_df = pd.read_csv(notes_path)
            print(f"成功读取 {notes_path}，共 {len(notes_df)} 条数据。")
        except Exception as e:
            print(f"读取 {notes_path} 失败: {e}")

    comments_df = pd.DataFrame()
    if os.path.exists(comments_path):
        try:
            # 尝试使用utf-8读取，失败则尝试gbk，并忽略错误
            try:
                comments_df = pd.read_csv(comments_path, encoding='utf-8')
            except UnicodeDecodeError:
                comments_df = pd.read_csv(comments_path, encoding='gbk', errors='replace')
            print(f"成功读取 {comments_path}，共 {len(comments_df)} 条数据。")
        except Exception as e:
            print(f"读取 {comments_path} 失败: {e}")

    # 合并笔记内容和评论内容，统一作为舆情分析文本
    texts = []
    
    if not notes_df.empty:
        for _, row in notes_df.iterrows():
            title = str(row.get('title', ''))
            content = str(row.get('content', ''))
            full_text = f"{title} {content}".replace('nan', '').strip()
            
            publish_time = str(row.get('publish_time', ''))
            ip_location = str(row.get('ip_location', ''))
            
            if full_text:
                texts.append({
                    'source_type': 'note',
                    'original_id': row.get('note_id', ''),
                    'text': clean_text(full_text),
                    'publish_time': publish_time,
                    'ip_location': ip_location
                })

    if not comments_df.empty:
        for _, row in comments_df.iterrows():
            # 修复：评论内容对应的列是 'comment_content'
            content = str(row.get('comment_content', ''))
            content = content.replace('nan', '').strip()
            
            publish_time = str(row.get('comment_time', ''))
            ip_location = str(row.get('commenter_ip_location', ''))
            
            if content:
                texts.append({
                    'source_type': 'comment',
                    'original_id': row.get('comment_id', ''),
                    'text': clean_text(content),
                    'publish_time': publish_time,
                    'ip_location': ip_location
                })
                
    cleaned_df = pd.DataFrame(texts)
    
    # 过滤掉清洗后为空或太短的文本（少于3个字符）
    cleaned_df = cleaned_df[cleaned_df['text'].str.len() >= 3]
    
    # 去重
    cleaned_df = cleaned_df.drop_duplicates(subset=['text'])
    
    output_path = 'cleaned_data.csv'
    cleaned_df.to_csv(output_path, index=False, encoding='utf-8-sig')
    print(f"清洗完成！共保留 {len(cleaned_df)} 条有效舆情文本，已保存至 {output_path}。")

if __name__ == '__main__':
    main()
