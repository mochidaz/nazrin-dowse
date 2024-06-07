from flask import Flask, request, render_template, stream_template, send_from_directory
import cloudscraper
from bs4 import BeautifulSoup
import urllib.parse

app = Flask(__name__, static_url_path='/media', static_folder='media')

class Track(object):
    def __init__(self, album, track_number, arrangement_title, translated_name, arrangement, source, vocals, lyrics, original_title, guitar, note, from_, lyrics_link):
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
        music_href = row.find('a')['href']
        music_title = row.find('a')['title']

        album_url = urllib.parse.urljoin(url, music_href)
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
                arrangement_title = "No Title"
                arrangement_info = [li.get_text(strip=True) for li in track.find_all('li')]
                lyrics_link = None
                track_number = "No Number"
                original_title = None
                translated_name = None
                arrangement = None
                source = None
                vocals = None
                lyrics = None
                stripped_original = None
                stripped_input = None
                guitar = None
                note = None
                from_ = None

                for info in arrangement_info:
                    try:
                        if 'original title:' in info:
                            original_title = info.split('original title:')[1].strip()
                            original_title = original_title.split('source:')[0].strip()
                            stripped_original = normalize_whitespace(original_title.lower())
                            stripped_input = normalize_whitespace(search_query.lower())

                            if stripped_input not in stripped_original:
                                continue
                        elif 'guitar:' in info:
                            guitar = info.split('guitar:')[1].strip()
                        elif 'arrangement:' in info:
                            arrangement = info.split('arrangement:')[1].strip()
                        elif 'source:' in info:
                            source = info.split('source:')[1].strip()
                        elif 'vocals' in info:
                            vocals = info.split('vocals:')[1].strip()
                        elif 'lyrics' in info:
                            lyrics = info.split('lyrics:')[1].strip()
                        elif 'note:' in info:
                            note = info.split('note:')[1].strip()
                        elif 'from' in info:
                            from_ = info.split('from:')[1].strip()
                        elif 'translated name:' in info:
                            translated_name = info.strip()
                    except Exception:
                        pass

                if original_title and stripped_input in stripped_original:
                    title_row = track.find('b')
                    if title_row:
                        arrangement_title = title_row.get_text(strip=True)
                        link = title_row.find('a')
                        track_number = title_row.previous_sibling.strip().split('.')[0]
                        if link :
                            lyrics_link = {
                                "link": urllib.parse.urljoin(url, link.attrs['href']),
                                "written": link.attrs['class'][0] if "class" in link.attrs else ""
                            }

                    yield Track(
                        album=music_title,
                        track_number=track_number,
                        arrangement_title=arrangement_title,
                        translated_name=translated_name,
                        arrangement=arrangement,
                        source=source,
                        vocals=vocals,
                        lyrics=lyrics,
                        original_title=original_title,
                        guitar=guitar,
                        note=note,
                        from_=from_,
                        lyrics_link=lyrics_link
                    )

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

if __name__ == '__main__':
    app.run(debug=True)
