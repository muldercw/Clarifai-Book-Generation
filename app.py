import base64
import os
import random
import re, uuid
from PIL import Image as PILImage
from clarifai.client.model import Model
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Image, PageBreak, Paragraph, SimpleDocTemplate, Spacer
import time
from uuid import uuid4


model_url = "https://clarifai.com/openai/chat-completion/models/gpt-4-turbo"
pat = "obtain pat through your clarifai account"
max_context_length = 128000  # Maximum context length allowed by the model 128000 #

def generate_text(prompt, model_url, pat):
    model = Model(url=model_url, pat=pat)
    response = model.predict_by_bytes(prompt.encode(), input_type="text")
    return response.outputs[0].data.text.raw

def generate_book_title(idea):
    prompt = "Write a single book title for a book about " + idea + "."
    return generate_text(prompt, model_url, pat)

def generate_synopsis(book_title):
    prompt = "Write a very short synopsis for a book titled " + book_title + "."
    return generate_text(prompt, model_url, pat)

def generate_chapter_titles(book_title, synopsis):
    prompt = "In a list, provide the 10 chapter's titles for the book " + book_title + " that you are going to create. And here is the synopsis: " + synopsis + "." +" Don not number the chapters, just write the titles."
    content = generate_text(prompt, model_url, pat).split("\n")
    chapter_titles = [title for title in content if title]
    return chapter_titles

def generate_chapter_summary(book_title, synopsis, chapter_titles, chapter_title, chapter_summaries):
    prompt = "Write a single sentence summary for the chapter titled " + chapter_title + " in the book " + book_title + "." + " And here is the synopsis: " + synopsis + "." +  " And here are the summaries for previous chapters: " + "\n".join([f"Chapter {i+1}: {title}" for i, title in enumerate(chapter_titles) if title in chapter_summaries])
    return generate_text(prompt, model_url, pat)

def generate_chapter_text(book_dict):
    for chapter_title in book_dict["chapters_titles"]:
        if chapter_title in book_dict["chapter_summaries"]:
            print(f"Writing chapter {chapter_title}")
            previous_chapters = [book_dict["chapter_summaries"][prev_chapter] for prev_chapter in book_dict["chapters_titles"][:book_dict["chapters_titles"].index(chapter_title)]]
            prev_chapters_summary = "\n".join([f"Chapter {i+1}: {title}" for i, title in enumerate(previous_chapters)])
            prompt = f"Write the text for chapter {chapter_title} titled " + chapter_title + ". Synopsis for the entire book: " + book_dict["synopsis"] + ". And here are the summaries for previous chapters: " + prev_chapters_summary + "." + "Ensure you write a minumum of 500 words for each chapter nad don't strat ech chapter off by saying its a new chpater ect. Ensure you format the paragraphs correctly."
            while len(prompt) > max_context_length:
                previous_chapters.pop(0)
                prev_chapters_summary = "\n".join([f"Chapter {i+1}: {title}" for i, title in enumerate(previous_chapters) if title is not None])
                prompt = "Write the text for the chapter titled " + chapter_title + ". Synopsis: " + book_dict["synopsis"] + ". Previous chapters: " + prev_chapters_summary
            content = generate_text(prompt, model_url, pat)
            chapter_text = {'chapter_title': chapter_title, 'chapter_text': content.replace("\n", "\n\n")}
            book_dict["chapter_texts"] = book_dict.get("chapter_texts", []) + [chapter_text]
    return book_dict
        
def generate_text_book(book_dict):
    filename = re.sub(r'[^\w\s]', '', book_dict["title"]).replace(" ", "_") + ".txt"
    with open(filename, "w") as f:
        f.write(book_dict["title"] + "\n\n")
        f.write(book_dict["synopsis"] + "\n\n")
        for chapter_text in book_dict["chapter_texts"]:
            f.write(chapter_text["chapter_title"] + "\n\n")
            f.write(chapter_text["chapter_text"] + "\n\n")

def summarizer(text):
    prompt = "Summarize the following text in less than 100 words: " + text
    return generate_text(prompt, model_url, pat)

def generate_image(prompt, folder_name):
    prompt = "Without showing any living animals or people (make-believe animals are ok), give me an image using this context:" + summarizer(prompt)
    inference_params = dict(quality="standard", size='1024x1024')
    model_urls = [
        "https://clarifai.com/stability-ai/stable-diffusion-2/models/stable-diffusion-xl-beta",
        "https://clarifai.com/gcp/generate/models/Imagen"
        "https://clarifai.com/openai/dall-e/models/dall-e-3",
        "https://clarifai.com/gcp/generate/models/imagen-2"
    ]
    for url in model_urls:
        try:
            immodel = (Model(url=url, pat=pat ))
            model_prediction = immodel.predict_by_bytes(prompt.encode(), input_type="text", inference_params=inference_params)
            output_base64 = model_prediction.outputs[0].data.image.base64
            filename = str(uuid.uuid4()) + '.png'
            image_path = os.path.join(folder_name, filename)
            with open(image_path, 'wb') as f:
                f.write(output_base64)
            image_path = resize_image(image_path)
            return image_path
        except Exception as e:
            print(f"Failed to generate image with model at URL {url}. Error: {e}")
            time.sleep(2)
    return None

def resize_image(image_path, max_width=400, max_height=400):
    img = PILImage.open(image_path)
    smallimage = img.resize((max_width, max_height))
    resized_image_path = os.path.join("images", os.path.basename(image_path))
    smallimage.save(resized_image_path)
    return resized_image_path

def should_generate_image():
    return random.choice([True, False, False, False, False])

def generate_pdf_book(book_dict):
    filename = re.sub(r'[^\w\s]', '', book_dict["title"]).replace(" ", "_") + ".pdf"
    doc = SimpleDocTemplate(filename, pagesize=letter)
    styles = getSampleStyleSheet()
    content = []
    title = book_dict["title"]
    title_image = generate_image(title, "images")
    title_text = Paragraph(title, styles['Title'])
    title_image = Image(title_image)
    content.append(title_text)
    content.append(Spacer(1, 12))
    content.append(title_image)
    content.append(PageBreak())
    toc_title = Paragraph("<u>Table of Contents</u>", styles['Heading1'])
    content.append(toc_title)
    chapter_number = 1
    for chapter_title in book_dict["chapters_titles"]:
        chapter_title_text = Paragraph(f"{chapter_number}. {chapter_title}", styles['Normal'])
        content.append(chapter_title_text)
        chapter_number += 1
    content.append(PageBreak())
    for chapter in book_dict["chapter_texts"]:
        chapter_title = chapter["chapter_title"]
        chapter_text = chapter["chapter_text"]
        chapter_summary = book_dict["chapter_summaries"].get(chapter_title, "")
        chapter_title_text = Paragraph(chapter_title, styles['Heading1'])
        paragraphs = [para.strip() for para in chapter_text.split("\n") if para.strip()]
        content.extend([chapter_title_text])
        for para in paragraphs:
            if should_generate_image(): #randomly generate an image
                image = generate_image(para, "images")
                image_obj = Image(image)
                content.append(image_obj)
                content.append(Paragraph(para, styles['Normal']))
            else:
                content.append(Paragraph(para, styles['Normal']))
        content.append(PageBreak())
    doc.build(content)
    print(f"PDF book '{filename}' generated successfully.")

def main(idea):
    book_dict = {}
    title = generate_book_title(idea)
    book_dict["title"] = title
    synopsis = generate_synopsis(title)
    book_dict["synopsis"] = synopsis
    chapters_titles = generate_chapter_titles(title, synopsis)
    book_dict["chapters_titles"] = chapters_titles
    chapter_summaries = {}
    for chapter_title in chapters_titles:
        print(chapter_title)
        chapter_summary = generate_chapter_summary(title, synopsis, chapters_titles, chapter_title, chapter_summaries)
        chapter_summaries[chapter_title] = chapter_summary
    book_dict["chapter_summaries"] = chapter_summaries
    book_dict = generate_chapter_text(book_dict)
    generate_text_book(book_dict)
    try:
        generate_pdf_book(book_dict)
    except Exception as e:
        print(f"Failed to generate PDF book. Error: {e}")

if __name__ == "__main__":
    main("a story about a magical wooden toothpick")
