from flask import Flask, request, render_template
import cloudscraper
from bs4 import BeautifulSoup
import urllib.parse

app = Flask(__name__, static_url_path='/media', static_folder='media')

class Track(object):
    def __init__(self, album, track_number, arrangement_title, translated_name, arrangement, source, vocals, lyrics, original_title):
        self.album = album
        self.track_number = track_number
        self.arrangement_title = arrangement_title
        self.translated_name = translated_name
        self.arrangement = arrangement
        self.source = source
        self.vocals = vocals
        self.lyrics = lyrics
        self.original_title = original_title

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

    rows = soup.find_all('tr', valign='top')
    found_tracks = []

    for row in rows:
        music_href = row.find('a')['href']
        music_title = row.find('a')['title']
        music_info = row.find('dd').text

        album_url = urllib.parse.urljoin(url, music_href)
        album_response = scraper.get(album_url)
        album_soup = BeautifulSoup(album_response.text, 'html.parser')

        track_lists = album_soup.find_all('ul')
        for track_list in track_lists:
            tracks = track_list.find_all('li', recursive=False)
            for track in tracks:
                track_number = track.find('b').previous_sibling.strip().split('.')[0] if track.find('b') else "No Number"
                arrangement_title = track.find('b').get_text(strip=True) if track.find('b') else "No Title"
                arrangement_info = [li.get_text(strip=True) for li in track.find_all('li')]
                original_title = None
                translated_name = None
                arrangement = None
                source = None
                vocals = None
                lyrics = None
                stripped_original = None
                stripped_input = None

                for info in arrangement_info:
                    if 'original title:' in info:
                        original_title = info.split('original title:')[1].strip()
                        original_title = original_title.split('source:')[0].strip()
                        stripped_original = normalize_whitespace(original_title.lower())
                        stripped_input = normalize_whitespace(search_query.lower())

                        if stripped_input not in stripped_original:
                            continue

                    elif 'arrangement:' in info:
                        arrangement = info.split('arrangement:')[1].strip()
                    elif 'source:' in info:
                        source = info.split('source:')[1].strip()
                    elif 'vocals' in info:
                        try:
                            vocals = info.split('vocals:')[1].strip()
                        except Exception as e:
                            pass
                    elif 'lyrics' in info:
                        lyrics = info.split('lyrics:')[1].strip()
                    else:
                        translated_name = info.strip()

                if original_title and stripped_input in stripped_original:
                    t = Track(
                        album=music_title,
                        track_number=track_number,
                        arrangement_title=arrangement_title,
                        translated_name=translated_name,
                        arrangement=arrangement,
                        source=source,
                        vocals=vocals,
                        lyrics=lyrics,
                        original_title=original_title
                    )
                    found_tracks.append(t)

    return found_tracks

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        url = request.form['url']
        search_query = request.form['search_query']
        tracks = search(search_query, url)
        return render_template('results.html', tracks=tracks)

    return render_template('index.html')

if __name__ == '__main__':
    app.run(debug=True)
