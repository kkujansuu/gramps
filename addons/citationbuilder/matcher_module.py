#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2024-2025      Kari Kujansuu
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.

import re
import shlex
import time
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from collections import defaultdict
from pprint import pprint

# https://stackoverflow.com/questions/36600583/python-3-urllib-ignore-ssl-certificate-verification
import ssl
ssl._create_default_https_context = ssl._create_unverified_context # for HisKi

def matches(line):
    for funcname, func in globals().items():
        if funcname.startswith("match_"):
            m = func(line)
            if m:
                return m
    return None


def maketitle(reponame, sourcetitle):
    if reponame.endswith("seurakunnan arkisto"):
        return (
            reponame.replace(" arkisto", " ") + sourcetitle[0].lower() + sourcetitle[1:]
        )
    if reponame.endswith("församlings arkiv"):
        return (
            reponame.replace(" arkiv", " ") + sourcetitle[0].lower() + sourcetitle[1:]
        )
    return "{} - {}".format(reponame, sourcetitle)


class Match:
    def __init__(self, line, reponame, sourcetitle, citationpage, details, url, date=None):
        self.line = line
        self.reponame = reponame
        self.sourcetitle = sourcetitle
        self.citationpage = citationpage
        self.details = details
        self.url = url
        self.date = date


def parse_html(htmlstring):

    class MyHTMLParser(HTMLParser):
        def __init__(self):
            super().__init__()
            self.items = {}
            self.items2 = defaultdict(list)
            self.count = 0
            self.tag = None

        def handle_starttag(self, tag, attrs):
            self.tag = tag

        def handle_endtag(self, tag):
            pass

        def handle_data(self, data):
            if self.count < 700:
                self.items[(self.tag, self.count)] = data
                self.items2[self.tag].append(data)
                self.count += 1

    parser = MyHTMLParser()
    parser.feed(htmlstring)
    return parser.items


def parse_html2(htmlstring):

    class MyHTMLParser(HTMLParser):
        def __init__(self):
            super().__init__()
            self.items = {}
            self.items2 = defaultdict(list)
            self.count = 0
            self.tags = []

        def handle_starttag(self, tag, attrs):
            print("--> start", tag)
            if tag in {"meta", "link"}:
                return
            self.tags.append(tag)

        def handle_endtag(self, tag):
            print("--> end", tag)
            while self.tags and self.tags[-1] != tag:
                self.tags = self.tags[:-1]
            if self.tags and self.tags[-1] == tag:
                self.tags = self.tags[:-1]
            print(self.tags)

        def handle_data(self, data):
            tag = ".".join(self.tags)
            if data.strip() == "":
                return
            if self.tags and self.tags[-1] in {"script", "style"}:
                return
            self.items[(tag, self.count)] = data
            self.items2[tag].append(data)
            self.count += 1

    parser = MyHTMLParser()
    parser.feed(htmlstring)
    return parser.items2

def match_narc1(line):
    # Liperin seurakunnan arkisto - Syntyneiden ja kastettujen luettelot 1772-1811 (I C:3), jakso 3: kastetut 1772 tammikuu; Kansallisarkisto: http://digi.narc.fi/digi/view.ka?kuid=6593368 / Viitattu 22.10.2018
    regex_narc = re.compile(
        "(.+?) - (.+?), jakso (.+); Kansallisarkisto: (.+) / Viitattu (.+)"
    )  # now I have two problems
    m = regex_narc.match(line)
    if not m:
        return None
    reponame = m.group(1)
    sourcetitle = maketitle(reponame, m.group(2))
    citationpage = "jakso " + m.group(3)
    url = m.group(4)
    details = f"Kansallisarkisto: {url}"
    return Match(line, reponame, sourcetitle, citationpage, details, url)


def match_narc2(line):
    # Lähdeviite aineistoon, ei kuvaan.
    # Kaatuneiden henkilöasiakirjat (kokoelma) - Perhonen Onni Aleksi, 16.10.1907; Kansallisarkisto: https://astia.narc.fi/uusiastia/kortti_aineisto.html?id=2684857838 / Viitattu 26.5.2022"
    regex_narc = re.compile(r"(.+?) - (.+?); Kansallisarkisto: (.+) / Viitattu (.+)")
    m = regex_narc.match(line)
    if not m:
        return None
    reponame = m.group(1)
    sourcetitle = maketitle(reponame, m.group(2))
    citationpage = m.group(2)
    url = m.group(3)
    details = f"Kansallisarkisto: {url}"
    return Match(line, reponame, sourcetitle, citationpage, details, url)


def match_sshy(line):
    # Tampereen tuomiokirkkoseurakunta - rippikirja, 1878-1887 (MKO166-181 I Aa:17) > 39: Clayhills tjenstespersoner; SSHY: http://www.sukuhistoria.fi/sshy/sivut/jasenille/paikat.php?bid=18233&pnum=39 / Viitattu 6.11.2018
    regex_sshy = re.compile(r"(.+) - (.+) > (.+?): (.*); SSHY: (.+) / Viitattu (.+)")
    m = regex_sshy.match(line)
    if not m:
        return None
    reponame = m.group(1)
    sourcetitle = "{} {}".format(reponame, m.group(2))
    citationpage = m.group(4).strip()
    url = m.group(5)
    details = f"SSHY: {url}"
    return Match(line, reponame, sourcetitle, citationpage, details, url)


def match_sshy2(line):
    # Tampereen tuomiokirkkoseurakunta rippikirja 1795-1800 (TK630 I Aa:2)  N:o 1 Häggman, Kask, Grefvelin ; SSHY http://www.sukuhistoria.fi/sshy/sivut/jasenille/paikat.php?bid=15950&pnum=8 / Viitattu 03.02.2022
    # Alastaro rippikirja 1751-1757 (JK478 I Aa1:3)  Sivu 10 Laurois Nepponen ; SSHY http://www.sukuhistoria.fi/sshy/sivut/jasenille/paikat.php?bid=15846&pnum=13 / Viitattu 03.02.2022
    regex_sshy = re.compile(
        r"(.+) ([\w-]+ \d{4}-\d{4} \(.+?\)) (.+); SSHY (http.+) / Viitattu (.+)"
    )
    m = regex_sshy.match(line)
    if not m:
        return None
    reponame = m.group(1)
    sourcetitle = "{} {}".format(reponame, m.group(2))
    citationpage = m.group(3).strip()
    url = m.group(4)
    details = f"SSHY: {url}"
    return Match(line, reponame, sourcetitle, citationpage, details, url)


def match_svar(line):
    # Hajoms kyrkoarkiv, Husförhörslängder, SE/GLA/13195/A I/12 (1861-1872), bildid: C0045710_00045
    if line.find("bildid:") < 0:
        return None
    i = line.find("bildid:")
    bildid = line[i:].split()[1]
    line = line.replace("bildid:", "SVAR bildid:")
    parts = line.split(",")
    reponame = parts[0]
    sourcetitle = ",".join(parts[0:3])
    citationpage = parts[3].strip()
    # https://sok.riksarkivet.se/bildvisning/C0060358_00162
    url = "https://sok.riksarkivet.se/bildvisning/" + bildid
    details = f"SVAR: {url}"
    return Match(line, reponame, sourcetitle, citationpage, details, url)

def match_kansalliskirjasto2(line):
    # Kansalliskirjasto viite yhtenä pötkönä, esim.
    #
    # Kurun Sanomat, 30.11.1939, nro 48, s. 1https://digi.kansalliskirjasto.fi/sanomalehti/binding/3040878?page=1Kansalliskirjaston digitaaliset aineistotViitattu:06.12.2024
    #
    # tai riveille jaettuna:
    #
    # Vasabladet, 18.11.1911, nro 138, s. 4
    # https://digi.kansalliskirjasto.fi/sanomalehti/binding/1340877?page=4
    # Kansalliskirjaston Digitoidut aineistot

    for reponame in [
        "Kansalliskirjaston Digitoidut aineistot",
        "Kansalliskirjaston digitaaliset aineistot",
        "Nationalbibliotekets digitala samlingar",
        "National Library's Digital Collections",
    ]:
        i = line.find(reponame)
        if i > 0:
            break
    if i < 0:
        return None
    line1 = line[:i]
    i = line1.find("http")
    line2 = line1[:i]
    url = line1[i:]

    i = line2.find(",")
    if i < 0:
        return None
    sourcetitle = line2[:i].strip()
    citationpage = line2[i + 1 :].strip()
    details = f"Kansalliskirjasto: {url}"
    return Match(line, reponame, sourcetitle, citationpage, details, url)


def match_geni(line):
    # Geni.com link
    #
    if line.startswith("https://www.geni.com/people/"):

        url = line
        i = url.find("?through")
        if i > 0:
            url = url[:i]
        name = line.split("/")[4].replace("-", " ")
        name = urllib.parse.unquote(name)
        sourcetitle = "Geni.com"
        citationpage = name
        details = url
        reponame = "Geni"
        return Match(line, reponame, sourcetitle, citationpage, details, url)


# familysearch
def match_familysearch(line):
    # "United States, Census, 1950", , FamilySearch (https://www.familysearch.org/ark:/61903/1:1:6X1G-K822 : Wed Mar 20 22:12:37 UTC 2024), Entry for Alfred L Kinney and Esther S Kinney, April 8, 1950.

    # "Find a Grave Index," database, FamilySearch (https://www.familysearch.org/ark:/61903/1:1:63PR-4NT2 : 18 December 2020), Augusta Heino, ; Burial, Camberwell, London Borough of Southwark, Greater London, England, Camberwell Old Cemetery; citing record ID 218217643, Find a Grave, http://www.findagrave.com.
    if not line.startswith('"'):
        return None
    if " FamilySearch " not in line:
        return None
    line = line.replace("'", "''")
    temp = shlex.split(line)
    print(temp)
    sourcetitle = temp[0].replace("''", "'")
    if sourcetitle.endswith(","):
        sourcetitle = sourcetitle[:-1]
    i = line.find("http")
    if i < 0:
        return None
    url = line[i:].split()[0]
    j = line.find("),", i)
    if j < 0:
        return None
    citationpage = line[j + 2 :].strip().replace("''", "'")
    reponame = "FamilySearch"
    details = line
    return Match(line, reponame, sourcetitle, citationpage, details, url)


def match_hiski(line):
    #    https://hiski.genealogia.fi/hiski/5k2oqz?fi+0114+kastetut+21
    #
    #    https://hiski.genealogia.fi/hiski?fi+t1791042
    #
    #    https://hiski.genealogia.fi/hiski/5k0bu8?fi+0114+kastetut+39708
    #
    #    https://hiski.genealogia.fi/hiski?fi+t1830723
    #     <h2>Iitti</h2>
    #     <h3>Kastetut</h3>
    #
    #     <p><a href="/hiski?fi+t1741187">Linkki tähän tapahtumaan</a> [ 1741187 ]</p>
    #
    #     <table border="4" bgcolor="#F5F5F5" cellspacing="0" cellpadding="2">
    #
    #     <tbody>
    #         <tr><td><small>Syntynyt / Kastettu</small> </td><td colspan="2">3.1.1847 </td><td colspan="3">15.1.1847</td></tr>
    #
    if not line.startswith("https://hiski.genealogia.fi"):
        return None

    htmlstring = urllib.request.urlopen(line).read().decode("iso8859-1")
    items = parse_html(htmlstring)

    #    pprint(items)
    #     ...
    #    ('a', 31): ' [ 10067970 ]',
    #
    #    ('h2', 26): 'Ikaalinen - Ikalis',
    #    ('h2', 27): '\n',
    #    ('h3', 28): 'Kastetut',
    #
    #     ('td', 35): '10.1.1900 ',
    #     ('td', 36): '10.1.1900',
    #     ('td', 37): '\n',
    #     ('td', 40): 'Isoröyhiö ',
    #     ('td', 41): 'Kukkasniemi',
    #     ('td', 42): '\n',
    #     ('td', 45): 'trp: ',
    #     ('td', 46): 'Taavetti ',
    #     ('td', 47): '\xa0 ',
    #     ('td', 48): 'Korpela ',
    #     ('td', 49): '\xa0',
    #     ('td', 50): '\n',
    #     ('td', 53): 'v:o ',
    #     ('td', 54): 'Hilda ',
    #     ('td', 55): '\xa0 ',
    #     ('td', 56): '\xa0 ',
    #     ('td', 57): '33',
    #     ('td', 58): '\n',
    #     ('td', 61): 'Oiva Johanneskaksoinen\n\n',
    #     ('td', 64): '\xa0\n',
    #     ('td', 67): '\xa0\n',
    #
    #

    #    parish = root.find('h2')
    #    print("parish", parish)

    parish = items[("h2", 26)]
    rectype = items[("h3", 28)]
    recid = items[("a", 31)][2:-1].strip()
    i = line.find("?")
    lang = line[i + 1 : i + 3]  # fi, se, en
    sourcetitle = parish + " HisKi " + rectype
    url = "https://hiski.genealogia.fi/hiski?" + lang + "+t" + recid
    citationpage = url
    reponame = "Hiskipalvelu"
    details = f"HisKi: {url}"
    return Match(line, reponame, sourcetitle, citationpage, details, url)


def match_katiha(line):
    # https://katiha.kansallisarkisto.fi/henkilotieto.php?keyId=0617R006a0000020
    if not line.startswith("https://katiha.kansallisarkisto.fi"):
        return None
    htmlstring = urllib.request.urlopen(line).read().decode("utf-8")
    items = parse_html2(htmlstring)
    sourcetitle = "Katiha"
    url = line
    citationpage = url
    reponame = "Kansallisarkisto"
    details = f"Katiha: {url}"
    return Match(line, reponame, sourcetitle, citationpage, details, url)


def xxxmatch_any(line):
    # any URL
    if not line.startswith("http"):
        return None
    url = line.split()[0]
    x = urllib.parse.urlparse(url)
    sourcetitle = x.netloc
    citationpage = url
    reponame = x.netloc
    details = line
    return Match(line, reponame, sourcetitle, citationpage, details, url)


if __name__ == "__main__":
    import sys

    url = sys.argv[1]
    m = matches(url)
    if m:
        pprint(m.__dict__)
