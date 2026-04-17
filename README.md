# W3Schools Quiz Scraper

This scraper downloads quiz questions from W3Schools quiz pages and saves them as JSON.

Run (from repository root):

```bash
python scrapers/scrape_w3schools_quizzes.py --start-url https://www.w3schools.com/ --output quizzes.json
```

Interactive quiz (headless Selenium):

```bash
python scrapers/scrape_w3schools_quiz_selenium.py --start-url "https://www.w3schools.com/quiztest/quiztest.asp?qtest=HTML" --output quizzes_selenium.json
```

Options:

- `--limit N` : stop after N quiz pages (useful for testing)

Notes:

- The script uses HTML heuristics; some quizzes that require JavaScript may not fully expose answers.
- Output `quizzes.json` contains objects with fields: `id`, `topic`, `question`, `options`, `correct`, `explanation`, `source`.
