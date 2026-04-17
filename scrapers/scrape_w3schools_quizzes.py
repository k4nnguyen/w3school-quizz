#!/usr/bin/env python3
"""Scrape W3Schools quiz pages and save quizzes as JSON.

Usage:
  python scrapers/scrape_w3schools_quizzes.py --start-url https://www.w3schools.com/ --output quizzes.json

Notes:
  - The script finds links matching *_quiz.asp or *_exercises.asp under the site.
  - It uses heuristics to extract questions, options, correct answer and explanation.
  - Some pages are heavily JS-driven; results may vary.
"""
import argparse
import json
import re
import time
from collections import defaultdict
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup


HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
}


def extract_corrects_from_result_html(html):
    """Parse a quiz result HTML page and return per-question option info.

    Returns a list of dicts: {"question": text, "options": [
        {"text": str, "correct": bool, "explanation": str|None}
    ]}
    """
    soup = BeautifulSoup(html, "html.parser")
    quizmain = soup.find(id="quizmain") or soup
    out = []
    # questions are rendered as <h3>Question N:</h3><p>...</p> followed by option divs
    for h in quizmain.find_all("h3"):
        htext = h.get_text(" ", strip=True)
        if not htext.lower().startswith("question"):
            continue
        try:
            p = h.find_next_sibling(lambda t: getattr(t, "name", None) == "p")
        except Exception:
            p = None
        qtext = p.get_text(" ", strip=True) if p else h.get_text(" ", strip=True)
        opts = []
        node = p.next_sibling if p is not None else h.next_sibling
        # iterate until hr or next h3
        while node:
            if getattr(node, "name", None) == "hr":
                break
            if getattr(node, "name", None) == "div":
                classes = node.get("class") or []
                if "radiocontainer" in classes:
                    span = node.find("span", class_="answercomment")
                    explanation = None
                    if span:
                        st = span.get_text(" ", strip=True)
                        if st and st.lower() not in ("your answer", "correct answer"):
                            explanation = st
                        span.extract()
                    text = node.get_text(" ", strip=True)
                    opts.append({"text": text, "correct": ("correct" in classes), "explanation": explanation})
            node = node.next_sibling
        if opts:
            out.append({"question": qtext, "options": opts})
    return out



def fetch(url, session=None, delay=0.3):
    s = session or requests.Session()
    resp = s.get(url, headers=HEADERS, timeout=20)
    time.sleep(delay)
    resp.raise_for_status()
    return resp.text


def find_quiz_links(start_url, session=None):
    html = fetch(start_url, session=session)
    links = set()
    pattern = re.compile(r"/[^/]+/[^/]+_(?:quiz|exercises)\.asp")
    
    # Just regex match the raw HTML to catch all links easily
    # even if they are dynamically injected or hidden in large menus
    for match in pattern.findall(html):
        links.add(urljoin(start_url, match))

    return sorted(links)


def lowest_common_ancestor(elements):
    if not elements:
        return None
    paths = [list(elem.parents) for elem in elements]
    # include element itself as possible parent
    paths = [[elements[i]] + paths[i] for i in range(len(elements))]
    # find first ancestor in first's path that appears in all others
    for ancestor in paths[0]:
        if all(ancestor in p for p in paths[1:]):
            return ancestor
    return None


def extract_question_from_block(block):
    # Question text: prefer headings, then paragraphs not inside labels
    q_text = ""
    for tagname in ("h1", "h2", "h3", "h4", "strong", "b"):
        tag = block.find(tagname)
        if tag and tag.get_text(strip=True):
            q_text = tag.get_text(" ", strip=True)
            break

    if not q_text:
        # fallback: first text node in block that's not part of a label or option
        texts = []
        for child in block.find_all(text=True, recursive=True):
            parent = child.parent
            if parent.name == "label":
                continue
            txt = child.strip()
            if len(txt) > 10:
                texts.append(txt)
        if texts:
            q_text = texts[0]

    # options: labels preferred
    options = []
    labels = block.find_all("label")
    if labels:
        for lab in labels:
            t = lab.get_text(" ", strip=True)
            if t:
                options.append(t)
    else:
        # fallback: radio/checkbox inputs and nearby text
        for inp in block.find_all("input", {"type": re.compile("radio|checkbox")}):
            text = ""
            # try following sibling text
            sib = inp.next_sibling
            if sib and isinstance(sib, str) and sib.strip():
                text = sib.strip()
            else:
                # label with for attribute?
                if inp.has_attr("id"):
                    lab = block.find("label", {"for": inp["id"]})
                    if lab:
                        text = lab.get_text(" ", strip=True)
            if text:
                options.append(text)

    # find explicit correct answer or explanation
    correct = None
    explanation = None
    # Search for text patterns
    txt_block = block.get_text("\n", strip=True)
    m = re.search(r"Correct answer[:\s]*([A-Za-z0-9].+)", txt_block, re.I)
    if not m:
        m = re.search(r"Answer[:\s]*([A-Za-z0-9].+)", txt_block, re.I)
    if m:
        correct = m.group(1).strip()

    # explanation heuristics
    m2 = re.search(r"Explanation[:\s]*(.+)", txt_block, re.I)
    if m2:
        explanation = m2.group(1).strip()

    return {
        "question": q_text,
        "options": options,
        "correct": correct,
        "explanation": explanation,
    }


def parse_quiz_page(url, session=None):
    html = fetch(url, session=session)
    soup = BeautifulSoup(html, "html.parser")
    # If this is an interactive quiz (quiztest), iterate by POSTing the quiz form
    form = soup.find("form", id="quizform")
    if form:
        # perform server-side navigation to collect all questions
        results = []
        s = session or requests.Session()
        action = form.get("action")
        action_url = urljoin(url, action)
        qnum = 1
        last_resp = None
        while True:
            qtext_tag = soup.find(id="qtext")
            if not qtext_tag:
                break
            qtext = qtext_tag.get_text(strip=True)
            options = []
            for lab in form.find_all("label", class_="radiocontainer"):
                inp = lab.find("input")
                val = inp.get("value") if inp else None
                text = lab.get_text(" ", strip=True)
                options.append({"value": val, "label": text})
            results.append({"question": qtext, "options": [o["label"] for o in options], "raw_options": options})

            # prepare POST payload with hidden inputs
            post = {}
            for inp in form.find_all("input"):
                name = inp.get("name")
                if not name:
                    continue
                t = inp.get("type", "").lower()
                if t == "hidden":
                    post[name] = inp.get("value", "")

            # select first option (we only need to advance pages)
            if options:
                first_inp = form.find("input", {"type": "radio"})
                radio_name = first_inp.get("name") if first_inp else "quiz"
                post[radio_name] = options[0]["value"]

            post["nextnumber"] = str(qnum + 1)
            last_resp = s.post(action_url, data=post, headers=HEADERS, timeout=20)
            soup = BeautifulSoup(last_resp.text, "html.parser")
            form = soup.find("form", id="quizform")
            qnum += 1
            if not form:
                break

        # try to parse the final result page (last_resp) to fill correct/explanation
        try:
            if last_resp is not None:
                # Sometimes there's an intermediate 'Check your answers' form
                check_form = BeautifulSoup(last_resp.text, "html.parser").find("form", action="result.asp")
                if check_form:
                    res_post = {}
                    for inp in check_form.find_all("input"):
                        if inp.get("name"):
                            res_post[inp.get("name")] = inp.get("value", "")
                    res_url = urljoin(last_resp.url, check_form.get("action"))
                    last_resp = s.post(res_url, data=res_post, headers=HEADERS, timeout=20)

                parsed = extract_corrects_from_result_html(last_resp.text)
                if parsed:
                    for idx, item in enumerate(results):
                        if idx < len(parsed):
                            parsed_opts = parsed[idx].get("options", [])
                            cor = None
                            expl = None
                            for opt in parsed_opts:
                                if opt.get("correct"):
                                    cor = opt.get("text")
                                    if opt.get("explanation"):
                                        expl = opt.get("explanation")
                                    break
                            if cor:
                                item["correct"] = cor
                                if expl:
                                    item["explanation"] = expl
        except Exception:
            pass

        return results
    # If no form, check if page links to the interactive quiz (Start link)
    start_link = None
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "quiztest.asp?qtest=" in href:
            start_link = urljoin(url, href)
            break
        txt = (a.get_text() or "").strip().lower()
        if (txt.startswith("start") and "quiz" in txt) or "start the quiz" in txt:
            start_link = urljoin(url, href)
            break
    if start_link:
        try:
            html2 = fetch(start_link, session=session)
            soup2 = BeautifulSoup(html2, "html.parser")
            form2 = soup2.find("form", id="quizform")
            if form2:
                # navigate interactive quiz starting from the quiztest URL
                results = []
                s = session or requests.Session()
                action = form2.get("action")
                action_url = urljoin(start_link, action)
                qnum = 1
                last_resp = None
                while True:
                    qtext_tag = soup2.find(id="qtext")
                    if not qtext_tag:
                        break
                    qtext = qtext_tag.get_text(strip=True)
                    options = []
                    for lab in form2.find_all("label", class_="radiocontainer"):
                        inp = lab.find("input")
                        val = inp.get("value") if inp else None
                        text = lab.get_text(" ", strip=True)
                        options.append({"value": val, "label": text})
                    results.append({"question": qtext, "options": [o["label"] for o in options], "raw_options": options})

                    post = {}
                    for inp in form2.find_all("input"):
                        name = inp.get("name")
                        if not name:
                            continue
                        t = inp.get("type", "").lower()
                        if t == "hidden":
                            post[name] = inp.get("value", "")

                    if options:
                        first_inp = form2.find("input", {"type": "radio"})
                        radio_name = first_inp.get("name") if first_inp else "quiz"
                        post[radio_name] = options[0]["value"]

                    post["nextnumber"] = str(qnum + 1)
                    last_resp = s.post(action_url, data=post, headers=HEADERS, timeout=20)
                    soup2 = BeautifulSoup(last_resp.text, "html.parser")
                    form2 = soup2.find("form", id="quizform")
                    qnum += 1
                    if not form2:
                        break

                # try to parse the final result page (last_resp) to fill correct/explanation
                try:
                    if last_resp is not None:
                        # Sometimes there's an intermediate 'Check your answers' form
                        check_form = BeautifulSoup(last_resp.text, "html.parser").find("form", action="result.asp")
                        if check_form:
                            res_post = {}
                            for inp in check_form.find_all("input"):
                                if inp.get("name"):
                                    res_post[inp.get("name")] = inp.get("value", "")
                            res_url = urljoin(last_resp.url, check_form.get("action"))
                            last_resp = s.post(res_url, data=res_post, headers=HEADERS, timeout=20)
                            
                        parsed = extract_corrects_from_result_html(last_resp.text)
                        if parsed:
                            for idx, item in enumerate(results):
                                if idx < len(parsed):
                                    parsed_opts = parsed[idx].get("options", [])
                                    cor = None
                                    expl = None
                                    for opt in parsed_opts:
                                        if opt.get("correct"):
                                            cor = opt.get("text")
                                            if opt.get("explanation"):
                                                expl = opt.get("explanation")
                                            break
                                    if cor:
                                        item["correct"] = cor
                                        if expl:
                                            item["explanation"] = expl
                except Exception:
                    pass

                return results
        except Exception:
            pass
    # collect all radio/checkbox inputs grouped by name (static pages)
    inputs = soup.find_all("input", {"type": re.compile("radio|checkbox")})
    groups = defaultdict(list)
    for inp in inputs:
        name = inp.get("name") or inp.get("id") or str(hash(inp))
        groups[name].append(inp)

    results = []
    for name, elems in groups.items():
        # find LCA block for this question
        block = lowest_common_ancestor(elems)
        if not block:
            continue
        q = extract_question_from_block(block)
        # skip empty questions
        if not q["question"] and not q["options"]:
            continue
        results.append(q)

    # Try alternate pattern: some pages show answers in elements with class containing 'question' or 'quiz'
    if not results:
        candidates = soup.select("div.question, div.quiz, section.question, section.quiz")
        for c in candidates:
            q = extract_question_from_block(c)
            if q["question"] or q["options"]:
                results.append(q)

    return results


def topic_from_url(url):
    path = urlparse(url).path
    parts = [p for p in path.split('/') if p]
    if parts:
        return parts[0]
    return url


def is_quiz_page(url):
    path = urlparse(url).path.lower()
    return path.endswith("_quiz.asp") or path.endswith("_exercises.asp")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--start-url", default="https://www.w3schools.com/", help="Start URL to discover quiz links")
    parser.add_argument("--output", default="quizzes.json", help="Output JSON file")
    parser.add_argument("--limit", type=int, default=0, help="Limit number of quiz pages to fetch (0 = all found)")
    args = parser.parse_args()

    session = requests.Session()
    if "quiztest" in args.start_url:
        quiz_links = [args.start_url]
    elif is_quiz_page(args.start_url):
        quiz_links = [args.start_url]
    else:
        quiz_links = find_quiz_links(args.start_url, session=session)
    print(f"Found {len(quiz_links)} quiz links")
    if args.limit > 0:
        quiz_links = quiz_links[: args.limit]

    out = []
    qid = 1
    for link in quiz_links:
        try:
            topic = topic_from_url(link)
            print(f"Parsing {link} (topic={topic})")
            questions = parse_quiz_page(link, session=session)
            for q in questions:
                out.append({
                    "id": qid,
                    "topic": topic,
                    "question": q.get("question"),
                    "options": q.get("options"),
                    "correct": q.get("correct"),
                    "explanation": q.get("explanation"),
                    "source": link,
                })
                qid += 1
        except Exception as e:
            print(f"Error parsing {link}: {e}")

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    print(f"Saved {len(out)} questions to {args.output}")


if __name__ == "__main__":
    main()
