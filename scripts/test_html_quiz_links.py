import requests
import bs4

html = requests.get('https://www.w3schools.com/html/html_quiz.asp').text
soup = bs4.BeautifulSoup(html, 'html.parser')
for a in soup.find_all('a'):
    txt = a.get_text(str, strip=True).lower()
    href = a.get('href', '')
    if 'quiz' in txt or 'quiz' in href:
        print(href, txt)

