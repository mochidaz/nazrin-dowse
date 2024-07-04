from flask import Flask, request, render_template, stream_template, send_from_directory, stream_with_context, Response, jsonify
import cloudscraper
from bs4 import BeautifulSoup
import urllib.parse

import json

app = Flask(__name__, static_url_path='/media', static_folder='media')

class ApiFormat:
    def __init__(self, count, data):
        self.count = count
        self.data = data

class Track(object):
    def __init__(self, album, track_number, arrangement_title, translated_name, arrangement, source, vocals, original_title, guitar, note, from_, genre, album_img, lyrics=None, lyrics_link=None):
        self.album = album
        self.track_number = track_number
        self.arrangement_title = arrangement_title
        self.translated_name = translated_name
        self.arrangement = arrangement
        self.source = source
        self.vocals = vocals
        self.lyrics = lyrics
        self.lyrics_link = lyrics_link
        self.original_title = original_title
        self.guitar = guitar
        self.note = note
        self.from_ = from_
        self.genre = genre
        self.album_img = "https://en.touhouwiki.net" + album_img


def normalize_whitespace(text):
    whitespace_chars = [
        '\u0020',  # Space
        '\u00A0',  # No-Break Space
        '\u1680',  # Ogham Space Mark
        '\u2000',  # En Quad
        '\u2001',  # Em Quad
        '\u2002',  # En Space
        '\u2003',  # Em Space
        '\u2004',  # Three-Per-Em Space
        '\u2005',  # Four-Per-Em Space
        '\u2006',  # Six-Per-Em Space
        '\u2007',  # Figure Space
        '\u2008',  # Punctuation Space
        '\u2009',  # Thin Space
        '\u200A',  # Hair Space
        '\u202F',  # Narrow No-Break Space
        '\u205F',  # Medium Mathematical Space
        '\u3000'  # Ideographic Space
    ]

    for ws_char in whitespace_chars:
        text = text.replace(ws_char, ' ')

    text = ''.join(text.split())
    return text.strip()

def search(search_query, url):
    scraper = cloudscraper.create_scraper()
    response = scraper.get(url)
    soup = BeautifulSoup(response.text, 'html.parser')
    
    rows = list(filter(lambda row: row.find('a'), soup.find_all('tr', valign='top')))
    albumCount = len(rows)
    yield "0/{}".format(albumCount)
    for i, row in enumerate(rows):
        yield "{}/{}".format(i,albumCount)
        album_href = row.find('a')['href']
        album_title = row.find('a')['title']
        album_image = row.find('img')['src']

        album_url = urllib.parse.urljoin(url, album_href)
        album_response = scraper.get(album_url)
        album_soup = BeautifulSoup(album_response.text, 'html.parser')

        if normalize_whitespace(search_query.lower()) not in normalize_whitespace(album_soup.text.lower().strip()):
            continue

        track_lists = album_soup.find_all('ul')
        for track_list in track_lists:
            if normalize_whitespace(search_query.lower()) not in normalize_whitespace(track_list.text.lower().strip()):
                continue

            tracks = track_list.find_all('li', recursive=False)
            for track in tracks:
                arrangement_title = track.find('b').get_text(strip=True) if track.find('b') else "No Title"
                lyrics_link = urllib.parse.urljoin(url, track.find('a').attrs['href']) if track.find('a') else None
                track_number = track.find('b').previous_sibling.strip().split('.')[0] if track.find('b') else "No Track Number"
                arrangement_info = [li.get_text(strip=True) for li in track.find_all('li')]
                original_title = set()
                translated_name = None
                arrangement = set()
                source = set()
                vocals = set()
                lyrics = set()
                stripped_original = set()
                stripped_input = None
                guitar = set()
                note = set()
                from_ = set()
                genre = set()

                for info in arrangement_info:
                    try:
                        if 'original title:' in info:
                            original_title_split = info.split('original title:')[1].strip()
                            original_title_split = original_title_split.split('source:')[0].strip()
                            stripped_original.add(normalize_whitespace(original_title_split.lower()))
                            stripped_input = normalize_whitespace(search_query.lower())

                            original_title.add(original_title_split.replace("\u3000", " "))

                            if stripped_input not in filter(lambda x: stripped_input in x, stripped_original):
                                continue
                        elif 'guitar:' in info:
                            guitar_split = info.split('guitar:')[1].strip()
                            guitar.add(guitar_split)
                        elif 'arrangement:' in info:
                            arrangement_split = info.split('arrangement:')[1].strip()
                            arrangement.add(arrangement_split)
                        elif 'source:' in info:
                            source_split = info.split('source:')[1].strip()
                            source.add(source_split)
                        elif 'vocals' in info:
                            vocals_split = info.split('vocals:')[1].strip()
                            vocals.add(vocals_split)
                        elif 'lyrics' in info:
                            lyrics_split = info.split('lyrics:')[1].strip()
                            lyrics.add(lyrics_split)
                        elif 'note:' in info:
                            note_split = info.split('note:')[1].strip()
                            note.add(note_split)
                        elif 'from' in info:
                            from_split = info.split('from:')[1].strip()
                            from_.add(from_split)
                        elif 'genre:' in info:
                            genre_split = info.split('genre:')[1].strip()
                            genre.add(genre_split)
                        else:
                            ja_span = track.find('span', {'lang': 'ja'})
                            if ja_span:
                                translated_name_elem = ja_span.find_next('i').find_next('i')
                                if translated_name_elem:
                                    translated_name = translated_name_elem.get_text(strip=True)

                    except Exception:
                        pass

                if original_title and filter(lambda x: stripped_input in x, stripped_original):
                    title_row = track.find('b')
                    if title_row:
                        arrangement_title = title_row.get_text(strip=True)
                        link = title_row.find('a')
                        track_number = title_row.previous_sibling.strip().split('.')[0]
                        if link :
                            lyrics_link = {
                                "link": urllib.parse.urljoin(url, link.attrs['href']),
                                "written": link.attrs['class'][0] if "class" in link.attrs else None
                            }

                    yield Track(
                        album=album_title,
                        track_number=track_number,
                        arrangement_title=arrangement_title,
                        translated_name=translated_name if translated_name else "-",
                        arrangement=", ".join(arrangement) if arrangement else "-",
                        source=", ".join(source) if source else "-",
                        vocals=", ".join(vocals) if vocals else "-",
                        original_title=", ".join(original_title) if original_title else "-",
                        guitar=", ".join(guitar) if guitar else "-",
                        note=", ".join(note) if note else "-",
                        from_=", ".join(from_) if from_ else "-",
                        genre=", ".join(genre) if genre else "-",
                        album_img=album_image,
                        lyrics_link=lyrics_link,
                        lyrics=", ".join(lyrics) if lyrics else "-",
                    )


def search(search_query, url):
    scraper = cloudscraper.create_scraper()
    response = scraper.get(url)
    soup = BeautifulSoup(response.text, 'html.parser')
    
    rows = list(filter(lambda row: row.find('a'), soup.find_all('tr', valign='top')))
    albumCount = len(rows)
    yield "0/{}".format(albumCount)
    for i, row in enumerate(rows):
        yield "{}/{}".format(i,albumCount)
        album_href = row.find('a')['href']
        album_title = row.find('a')['title']
        album_image = row.find('img')['src']

        album_url = urllib.parse.urljoin(url, album_href)
        album_response = scraper.get(album_url)
        album_soup = BeautifulSoup(album_response.text, 'html.parser')

        if normalize_whitespace(search_query.lower()) not in normalize_whitespace(album_soup.text.lower().strip()):
            continue

        track_lists = album_soup.find_all('ul')
        for track_list in track_lists:
            if normalize_whitespace(search_query.lower()) not in normalize_whitespace(track_list.text.lower().strip()):
                continue

            tracks = track_list.find_all('li', recursive=False)
            for track in tracks:
                arrangement_title = track.find('b').get_text(strip=True) if track.find('b') else "No Title"
                lyrics_link = urllib.parse.urljoin(url, track.find('a').attrs['href']) if track.find('a') else None
                track_number = track.find('b').previous_sibling.strip().split('.')[0] if track.find('b') else "No Track Number"
                arrangement_info = [li.get_text(strip=True) for li in track.find_all('li')]
                original_title = set()
                translated_name = None
                arrangement = set()
                source = set()
                vocals = set()
                lyrics = set()
                stripped_original = set()
                stripped_input = None
                guitar = set()
                note = set()
                from_ = set()
                genre = set()

                for info in arrangement_info:
                    try:
                        if 'original title:' in info:
                            original_title_split = info.split('original title:')[1].strip()
                            original_title_split = original_title_split.split('source:')[0].strip()
                            stripped_original.add(normalize_whitespace(original_title_split.lower()))
                            stripped_input = normalize_whitespace(search_query.lower())

                            original_title.add(original_title_split.replace("\u3000", " "))

                            if stripped_input not in filter(lambda x: stripped_input in x, stripped_original):
                                continue
                        elif 'guitar:' in info:
                            guitar_split = info.split('guitar:')[1].strip()
                            guitar.add(guitar_split)
                        elif 'arrangement:' in info:
                            arrangement_split = info.split('arrangement:')[1].strip()
                            arrangement.add(arrangement_split)
                        elif 'source:' in info:
                            source_split = info.split('source:')[1].strip()
                            source.add(source_split)
                        elif 'vocals' in info:
                            vocals_split = info.split('vocals:')[1].strip()
                            vocals.add(vocals_split)
                        elif 'lyrics' in info:
                            lyrics_split = info.split('lyrics:')[1].strip()
                            lyrics.add(lyrics_split)
                        elif 'note:' in info:
                            note_split = info.split('note:')[1].strip()
                            note.add(note_split)
                        elif 'from' in info:
                            from_split = info.split('from:')[1].strip()
                            from_.add(from_split)
                        elif 'genre:' in info:
                            genre_split = info.split('genre:')[1].strip()
                            genre.add(genre_split)
                        else:
                            ja_span = track.find('span', {'lang': 'ja'})
                            if ja_span:
                                translated_name_elem = ja_span.find_next('i').find_next('i')
                                if translated_name_elem:
                                    translated_name = translated_name_elem.get_text(strip=True)

                    except Exception:
                        pass

                if original_title and filter(lambda x: stripped_input in x, stripped_original):
                    title_row = track.find('b')
                    if title_row:
                        arrangement_title = title_row.get_text(strip=True)
                        link = title_row.find('a')
                        track_number = title_row.previous_sibling.strip().split('.')[0]
                        if link :
                            lyrics_link = {
                                "link": urllib.parse.urljoin(url, link.attrs['href']),
                                "written": link.attrs['class'][0] if "class" in link.attrs else None
                            }

                    yield Track(
                        album=album_title,
                        track_number=track_number,
                        arrangement_title=arrangement_title,
                        translated_name=translated_name if translated_name else "-",
                        arrangement=", ".join(arrangement) if arrangement else "-",
                        source=", ".join(source) if source else "-",
                        vocals=", ".join(vocals) if vocals else "-",
                        lyrics=", ".join(lyrics) if lyrics else "-",
                        original_title=", ".join(original_title) if original_title else "-",
                        guitar=", ".join(guitar) if guitar else "-",
                        note=", ".join(note) if note else "-",
                        from_=", ".join(from_) if from_ else "-",
                        lyrics_link=lyrics_link,
                        genre=", ".join(genre) if genre else "-",
                        album_img=album_image
                    )

def search_api(search_query, url):
    scraper = cloudscraper.create_scraper()
    response = scraper.get(url)
    soup = BeautifulSoup(response.text, 'html.parser')
    
    rows = list(filter(lambda row: row.find('a'), soup.find_all('tr', valign='top')))
    albumCount = len(rows)
    for i, row in enumerate(rows):
        album_href = row.find('a')['href']
        album_title = row.find('a')['title']
        album_image = row.find('img')['src']

        album_url = urllib.parse.urljoin(url, album_href)
        album_response = scraper.get(album_url)
        album_soup = BeautifulSoup(album_response.text, 'html.parser')

        if normalize_whitespace(search_query.lower()) not in normalize_whitespace(album_soup.text.lower().strip()):
            continue

        track_lists = album_soup.find_all('ul')
        for track_list in track_lists:
            if normalize_whitespace(search_query.lower()) not in normalize_whitespace(track_list.text.lower().strip()):
                continue

            tracks = track_list.find_all('li', recursive=False)
            for track in tracks:
                arrangement_title = track.find('b').get_text(strip=True) if track.find('b') else "No Title"
                lyrics_link = urllib.parse.urljoin(url, track.find('a').attrs['href']) if track.find('a') else None
                track_number = track.find('b').previous_sibling.strip().split('.')[0] if track.find('b') else "No Track Number"
                arrangement_info = [li.get_text(strip=True) for li in track.find_all('li')]
                original_title = set()
                translated_name = None
                arrangement = set()
                source = set()
                vocals = set()
                lyrics = set()
                stripped_original = set()
                stripped_input = None
                guitar = set()
                note = set()
                from_ = set()
                genre = set()

                for info in arrangement_info:
                    try:
                        if 'original title:' in info:
                            original_title_split = info.split('original title:')[1].strip()
                            original_title_split = original_title_split.split('source:')[0].strip()
                            stripped_original.add(normalize_whitespace(original_title_split.lower()))
                            stripped_input = normalize_whitespace(search_query.lower())

                            original_title.add(original_title_split.replace("\u3000", " "))

                            if stripped_input not in filter(lambda x: stripped_input in x, stripped_original):
                                continue
                        elif 'guitar:' in info:
                            guitar_split = info.split('guitar:')[1].strip()
                            guitar.add(guitar_split)
                        elif 'arrangement:' in info:
                            arrangement_split = info.split('arrangement:')[1].strip()
                            arrangement.add(arrangement_split)
                        elif 'source:' in info:
                            source_split = info.split('source:')[1].strip()
                            source.add(source_split)
                        elif 'vocals' in info:
                            vocals_split = info.split('vocals:')[1].strip()
                            vocals.add(vocals_split)
                        elif 'lyrics' in info:
                            lyrics_split = info.split('lyrics:')[1].strip()
                            lyrics.add(lyrics_split)
                        elif 'note:' in info:
                            note_split = info.split('note:')[1].strip()
                            note.add(note_split)
                        elif 'from' in info:
                            from_split = info.split('from:')[1].strip()
                            from_.add(from_split)
                        elif 'genre:' in info:
                            genre_split = info.split('genre:')[1].strip()
                            genre.add(genre_split)
                        else:
                            ja_span = track.find('span', {'lang': 'ja'})
                            if ja_span:
                                translated_name_elem = ja_span.find_next('i').find_next('i')
                                if translated_name_elem:
                                    translated_name = translated_name_elem.get_text(strip=True)

                    except Exception:
                        pass

                if original_title and filter(lambda x: stripped_input in x, stripped_original):
                    title_row = track.find('b')
                    if title_row:
                        arrangement_title = title_row.get_text(strip=True)
                        link = title_row.find('a')
                        track_number = title_row.previous_sibling.strip().split('.')[0]
                        if link :
                            lyrics_link = {
                                "link": urllib.parse.urljoin(url, link.attrs['href']),
                                "written": link.attrs['class'][0] if "class" in link.attrs else None
                            }

                    t = Track(
                        album=album_title,
                        track_number=track_number,
                        arrangement_title=arrangement_title,
                        translated_name=translated_name if translated_name else "-",
                        arrangement=", ".join(arrangement) if arrangement else "-",
                        source=", ".join(source) if source else "-",
                        vocals=", ".join(vocals) if vocals else "-",
                        original_title=", ".join(original_title) if original_title else "-",
                        guitar=", ".join(guitar) if guitar else "-",
                        note=", ".join(note) if note else "-",
                        from_=", ".join(from_) if from_ else "-",
                        genre=", ".join(genre) if genre else "-",
                        album_img=album_image
                    )

                    yield json.dumps({
                        'count': i,
                        'data': vars(t)
                    }) + '\n'

class Counter:
    def __init__(self):
        self.count = 0

    def increment(self):
        self.count += 1

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        url = request.form['url']
        search_query = request.form['search_query']
        tracks = search(search_query, url)
        counter = Counter()

        def generate(counter):
            for track in tracks:
                if type(track) is not str: 
                    counter.increment()
                yield track
            yield counter.count

        return stream_template('results.html', tracks=generate(counter))

    return render_template('index.html')

@app.route('/google1faec20f7ffb55d9.html')
def google():
    return send_from_directory('templates', 'google1faec20f7ffb55d9.html')

@app.route('/media/<path:filename>')
def media(filename):
    return send_from_directory('media', filename)

@app.route("/api/search", methods=['GET'])
def api_search():
    url = request.args.get('url')
    search_query = request.args.get('search_query')
    #tracks = search(search_query, url)
    counter = Counter()

    # def generate(counter):
    #     for track in tracks:
    #         if type(track) is not str and type(track) is not int:
    #             counter.increment()
    #             new_dict = vars(track)
    #             yield json.dumps({
    #                 'count': counter.count,
    #                 'data': new_dict
    #             }) + '\n'

    return Response(stream_with_context(search_api(search_query, url)), status=200, content_type='application/json')

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')
