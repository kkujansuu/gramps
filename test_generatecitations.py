from addons.generatecitations import matcher

def test_narc():
    text = "Liperin seurakunnan arkisto - Syntyneiden ja kastettujen luettelot 1772-1811 (I C:3), jakso 3: kastetut 1772 tammikuu; Kansallisarkisto: http://digi.narc.fi/digi/view.ka?kuid=6593368 / Viitattu 22.10.2018"
    m = matcher.matchline(text.splitlines())
    assert m is not None

    assert m.reponame == "Liperin seurakunnan arkisto"
    assert m.sourcetitle == "Liperin seurakunnan syntyneiden ja kastettujen luettelot 1772-1811 (I C:3)"
    assert m.citationpage == "jakso 3: kastetut 1772 tammikuu" 
    assert m.date == "22.10.2018"
    assert m.details == "Kansallisarkisto: http://digi.narc.fi/digi/view.ka?kuid=6593368 / Viitattu 22.10.2018"
    assert m.url == "http://digi.narc.fi/digi/view.ka?kuid=6593368"