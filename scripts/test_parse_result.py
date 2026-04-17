from scrapers.scrape_w3schools_quizzes import extract_corrects_from_result_html

p = 'G:/z/Python/Project/Crawl_Quizz_W3/tmp_result_page2.html'
html = open(p, encoding='utf-8').read()
parsed = extract_corrects_from_result_html(html)
print('questions', len(parsed))
for i,q in enumerate(parsed[:8]):
    print('\nQ', i+1, q['question'])
    for opt in q['options']:
        print('  ', opt['correct'], opt['text'], 'EXPL->', opt.get('explanation'))
