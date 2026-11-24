#!/usr/bin/env python3
"""Check the approved tavern exports, their skinning and their runtime atlases.

Owner decision of 2026-11-17 on the triangle budget (INGAME-QS-10 A1c): the innkeeper goes from 248891 to 33291
triangles with no visible change from the game camera. His cloth (TavernHood, TavernCloth) was modelled as closed shells
of two layers 1-2 mm apart; the outer layer is kept and decimated and the inner one rebuilt as its reversed copy, so the
inside of hood, sleeves and apron stays drawn with back faces culled. Checked here on the delivered file:
  budget        20000 to 35000 triangles, counts per material fixed from the reviewed export
  inside drawn  at least INNKEEPER_MIN_REVERSED of the cloth triangles have a reversed twin on the same three vertex
                positions (export 0.779; a mesh with only the outer layer has 0)
  look          a small software render of the bind pose from the game camera and from the front (flat atlas colour,
                two-sided Lambert light, back faces culled like the game) differs from the stored render of the
                innkeeper before the reduction by a mean of at most RENDER_MAX_MEAN_DIFFERENCE per channel and covers
                its silhouette by at least RENDER_MIN_SILHOUETTE_OVERLAP (intersection over union)

The tavern meshes and atlases come from the tavern room package, TavernObjects.material from the content packages
(scripts/content_packages.py); without the tavern room package only the navigation bounds are checked and the rest is
named as not checked.
"""

from array import array
import base64
import hashlib
import json
import math
import os
from pathlib import Path
import re
import struct
import subprocess
import tempfile
import time
import xml.etree.ElementTree as ET
import zlib

import numpy as np
from PIL import Image


ROOT = Path(__file__).resolve().parents[2]
import sys
sys.path.insert(0, str(ROOT / 'scripts'))
import content_packages  # noqa: E402
import room_packages  # noqa: E402

#: The assets of the tavern come from its room package (scripts/room_packages.py); without the package only the code
#: side is checked
ROOM_ASSETS = room_packages.has_room(ROOT, 'Tavern')


def room_file(relative):
    """A file of the game data, or of the content or room package when it moved there."""
    return content_packages.resolve(ROOT, relative)
# Fixed counts and bounds measured from the native serializer round trip.
MESHES = {
    'Innkeeper': (46676, 33291,
                  (-0.23106, -0.130789, 0.00475032),
                  (0.230241, 0.318891, 0.790697),
                  {'TavernSkin', 'TavernHood', 'TavernCloth'}),
    'TavernCounter': (53071, 43424,
                     (-0.52, -0.338, 0.0),
                     (0.520001, 0.0549586, 0.412484),
                     {'TavernCounterWood', 'TavernRail', 'TavernSign'}),
}
ATLASES = {'TavernSkin': 2048, 'TavernHood': 2048, 'TavernCloth': 2048,
           'TavernCounterWood': 2048, 'TavernRail': 1024, 'TavernSign': 512}
CLIPS = {'Idle': 4.0, 'Pour': 2.0, 'Cheer': 2.0}
# Triangle budget of the innkeeper (owner decision 2026-11-17) and the reviewed export of package A1c
INNKEEPER_BUDGET = (20000, 35000)
INNKEEPER_TRIANGLES = {'TavernSkin': 17376, 'TavernHood': 6683, 'TavernCloth': 9232}
INNKEEPER_SHA256 = '9859b7b755971e6c7bd2ce462a8de6ddff83ea0ed65d3562b740ed06e44bd2dc'
INNKEEPER_CLOTH = ('TavernHood', 'TavernCloth')
INNKEEPER_MIN_REVERSED = 0.7      # cloth triangles with a reversed twin (export 0.779; before the reduction 0.0)
# Render comparison against the innkeeper before the reduction (bind pose, flat atlas colour, two-sided light)
RENDER_PIXEL = 0.006
RENDER_HALF_WIDTH = 0.3
RENDER_LIGHT = (-0.4, -0.6, 0.7)
RENDER_AMBIENT = 0.35
VIEWS = {'game': ((0.0, math.sin(math.radians(25)), -math.cos(math.radians(25))),
                  (0.0, math.cos(math.radians(25)), math.sin(math.radians(25))), -0.2, 0.7),
         'front': ((0.0, 1.0, 0.0), (0.0, 0.0, 1.0), 0.0, 0.82)}
RENDER_MAX_MEAN_DIFFERENCE = 4.0  # export: game 1.72, front 3.09
RENDER_MIN_SILHOUETTE_OVERLAP = 0.97  # export: game 0.988, front 0.994
RENDER_REFERENCE = {  # zlib + base64 of the uint8 render of the innkeeper before the reduction (reviewed 2026-11-17),
    # rendered again from the same pre-reduction mesh with the atlases of INGAME-QS-11 K8, parts coloured in Blender
    # (owner decision 2026-11-18 "Neues Referenzbild, Grenze 4,0"; measured game 1.93, front 2.91)
    'game': ((150, 100, 3), (
        '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'
    )),
    'front': ((137, 100, 3), (
        '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'
        'BXbQhhwCoyLnqMqiWdnf5hVbAxeuevPLr2StrZgUoWR5IKw+82FZ6lDa+k4oRNVpBqpS9E2Nk8rybdGQoTEl63zTBMMipove9Ses'
        'svfKJDZuHY4GrcCqyXFnwWrbZklWQloZKMmK/8LVFQlKGid4tuy3yVoKO3Y1n41E70lWbMgRMRpiUVbL/Eotk6chYysbPKIo6DRD'
        'x1QXkw6XXo5if5azNaolUYDETuybp+sxxdp83PZtPQ0d9MOF5ly4bBLR1qRbAYqsm4ae7R9++1FUL56tB6NOCLHLo/H5eviDb7wm'
        '8wewS1YSFKcAKCdrTYg/H33z9dWkdbEeHs07x4vuoOnndl6J3TqXwBWp+D5XSooKncMAvUligGIP5Dmw4vh1rdKIXSrNQSeJfKsq'
        'pqFWPsOJu0Ln5Xzkm4N25Nv1duplPXJ66JqhZ5az4xQhXS1viW3DNaAkq2krmMZ1q7L/8Pby/tnsbDXoN/3jRY+Ns1V/OUyPp02M'
        'i03y1g6tYdOfdaM+BfUgbceOa9ZgBahJN1qNm2fLXlgvpaYCq4Zr8D9yyUrZtBDJShdeJoYR0SFpA79czXoceRranMW4J2al9lpR'
        'Xa3IGPJZsaoVc6NeamjK4aI/GzZXs+6wE6/n/eW0K4fwUJdkJaOH7AmR2aNsgEQ+5tYbltIwy+fLwYOz+Z2jCaxWk+ZikBwM00Hq'
        'zDpBP7G7kR07WosWJHEyVt6wFTR8Y9wO+BjR8q27q27iworYXivucRUkK9k+gkvPIr+ZpRmi/0qUOQoqWs97w25yebpYzXuwQlSR'
        'Z4opXlr1M8y1EJWo0boJDni2mch5wsNO0muFrhhkqXCc+KlsociISrkdSwisIHMJ2TP53Xcv/+TDr90/GgW2dv90eud4fPtwJFlh'
        'ncCIdCXKulKFP3o6sRFQrchuhZZkRfF4/3j8zp3loOXDCpJN38ABwcXJcr2IXeCSisqyQQW/lgOvcWCdbsYHk+5i3Gk3fDaozQFF'
        'ewCrz7Dk4eTZLbU/Ub0ROaFrdBthM3bxSq1Wrmes1KwppJWR8Y1Qk03zUKTR8C26waIXHQ2T00Xn7vH49KD36vn8dNkDTmwoiVXF'
        'IjGFRsQu4nlka5FTB1Q3cdqRPetFxOe37izHTQ83fHA2m3YCWJHyCTi4XnZDCs3olhWeJYMY0R4HPF6OOIXJoBkHNvGKMKKUC4X8'
        'fiyams+MlZJ5dBo5XIvNoo/L4334I554MO2K+VFahc+4nwzG6aLjSLDqijznCavIrCKedS/sRebhpHl5OLp7NL5zOJr3IolLmK4E'
        'WsnXSjYZV2EPI9Pupy6iYidUoGezVuLqiO1o2joYJsjmoBeJTrxshkPW85kTiccnaQBNkhzzaic+iqLtO5h0zHoVwwcpXH3HcOoi'
        '4/3sWAmFczBcF1ye8A6rbjPADUVrGDmi+8Uznu5bJsSRAm1ZkTm3ndoksTZtt2+rs9Q5JPi0/PN5Z55aw8h8gosPqyW3WsRM8tjC'
        'flQlgNfwx+N+NLZVL+tp34ybj24tPLM2J84Pk2oWw6tPsXrGp6SuoIxH4A6eVUdRuJ5Rp7TMw/MzzBlkEyNG2A213wqnwyaRCo2J'
        'mS3jdugZulZ9ph+e0lWyyrrXgFCeJ9btYdT3NFgNXO18lKx60ckoPWg6E1s96frj0Dju+NJGVm3q1Q9bbtdRz3rBrVHMd1eh2bBr'
        '60FyPms9upjBiuZyPYhpCCQrAe3XscpGG/1xv8El9hydg7f0GmG2l02E/jzydqRliNmwYiB4PmrJKXmwYkP71fn5gJLTFTJdVUli'
        'Q600CuvHXW/TcqeRcWccP5imF5M0NquH/RBWi9Bo29VFYi5TS3AL9IGjHjYdWB11vOOufzqIgmrxZJQQ8WD16vGoE9mH4+b5vEVd'
        'TMb+NKtncgB8gQOmGTo7nLBBWggoU6/Zn/NtBQiMi4L34fi0huN+irwdS3v6M4BK7HokWnMxi48Cv+fUYHWQWodtdxYadycJrC5H'
        '8ckwPhuns9Q+abnoahobo6Ded9WOU+u5atNSxpExbzjdQG+Y1YPUPh4mZ7P2xUH3zrp/Mmmeztqbfhxkdx2Wc3uYTKjUX40/fTEj'
        'brie9bOZlpZtqmr1Bd18USrkmomH79MmIq3poBk+Fay2rJLsviTJqqOVm1Z1kVo9T1s1bVjdGoSwOhsll/PWrWljit4AFZuwGkTm'
        'ILGHqS1ZTRoOuJYt72zSOJ21ACVZDVN3M4glK66gZCXavn/FijYI8YNrNmyR8NimRtv34rqRh+KerPsXK9pEU0zXF1PLCPJPs6J2'
        'y+ak1VBX367RwHHusMIHz/shrJYt5+5BBwPUohNIVoDiR7+Sh9Wk5QFKsmq6KqwkqNvLXts31sNk2iCgaUatJFmRf37C6kk7SNuH'
        'ljbzfhJY81GbSCsDyAsDhd9xmWyj9uj+SeDo60U/cE2OCnkbdWXYTbP5QgXJSnSnuzpFLk0YrDqOCitC0KblHPYCQM3b/hNWTReD'
        '1aIbblmRZmCTprsZJsOWP+1GwtpBW4wEIV1tENtupiuZSsk2EVYg6rcjgvm4lww6scg/RZ4z8Ow6F5f86sWwWoza73/lrtBzw+cw'
        'EFjsW5m0QpmAcZAUYE5W4MgyB1bjUBc+Fda7Tm3s12FFCrHuR7DqhgZk+rE1bXn3D4dbVifT5jB1JKuGpZJogYvKUbJit2IuhFmr'
        'Zf3nT7PikKjDcbe750gwsuolIaoBzXdESH/tcpP4+othlQQ2TcnhcniyHrcbojX0rKq4q7SbEAcgtpx2psPWIFDrxd2BrzbMCiWz'
        'Ud5zq/lYL9nKvlbcCevFll1pWGU+YFX22mIeozJLDaeaG0X1vq923Kql7CdGiQ94al4r7jrVfMPiK0pilttuVS3u6OV9Vy1yIbTS'
        'fnHvBj+W92+mkQ0Z8swvv/If0BJ8zg8nKErXlPOjmWvVL45mlGwvLFjhbuTAqKtaLkIJl1xNqUxjoj2VuyMamhJlslrYAYIYcFH2'
        '57FJcoWuRAOnV7qu2o/Mpquldq3lalg7pGBxzg+6k5aPSVElJmSqiGrUcDGSz6NJ8/Z6cDTvLPoJGkt8o+tWTSVXzt30tOL+zg28'
        '7Gg5JI2xDPVsMyXnnGUHDKvAqYWeCUmi1oth9afffR2Xx+++/viUH//wq5fS/b/1zjnvpDGNyFVKe1sfHEbGYdtJDSU1FXD9khXp'
        'QWQue+Gi7WOwInGSrJb9SIKiUWiYSsOoAsos52BF4IIVhktGhCzfePPO6mTRJf0jTIlBSbVI2VXLsoIPv3aX92aof+OtMzb+6w/e'
        '4k+Usd97//LFsKopT4Y/CjnRlQE3zxbuX60U5e+5duQJThbVifN9wlGgtSyFbAGxbRoOWdZBw542Reg+GiWAOh6ltw662JYVNdGW'
        'Fc7r1gqUP5IVadV6mDYDkzrxfNb+yYdvbyYtWFGEwoqoRaq5TW9EP0m1LBMq1PWkYr0y80hpBOU0GMnqctU/aHuJUX590Tzv++uW'
        'YEVhuOxF4Jp3fKTF6QOKihhWEpRk5dUKUb0MKAxoA78+TaxJat9d9daj9GTeofr+4N3LwBQ9/HLA8dqtTgArL9MV4Yi8sRdbbBCy'
        'Xps3RoF2Pkmx26veH9xfPzybCkUte4CSNm86khXtJqwSA4fVup4GqHXLvRhGt4bh8TAapE6/4U064cWyF9uqIQZtxczb68Uqm+8h'
        'BpsCowqis3n7oBc1bNWpFjhfUkry7Xub/hvnM+zh+fRyPbi16p9QsIwb2KIdrHsBNRFpxjQ2AbVIbTJVyudZbGBkHa7ocCg59Uo7'
        'NC+XXWolRy2V8/vYixl//6xecsRk2vR5bwfG48uDeTuYNL2GVcV9lv0YO+hHm1HjG2+evnN3eThM7q5754sO9pWL+ZvnM5wUo9aG'
        'zKphr5vOccebhHVSWRoIvZxTi3t6Yd8u5ycUQZEBK7smupHF+jPUhtdHWhLUKHVDs4qnPDgewep43DieNInMrx6N8Lhh02uFZuzW'
        'V8OEXJ3CuReZ2MOzyYOj4Wub/iIxR77Ge89Tfa1kVnL10j5mVQtGJYf1/XpDr6yazpZV9clQTu66SAvXm7VCceObVobV+w82W1ap'
        'WwfXxaLz2snkfN4eJnbDqwtzNDwUjNitZffyQNii5Qaig7Sg5He3Foo4XwQUjilYIdTQkNKClRzSBResrsWdmICiBYRV09W7fv29'
        'e8uzeWfU9s+mLepoyep0lMiZ8Iku2jhOuWlVqXFagYnJCQBQcqrk5AUMp8P1jHIOc4V+9nFGWEV6BVYn4xRXnTddSy1lnVc50eFw'
        '5ZcH8XVxf24qJp4Ju73q3zse39kMYSXHdLAtK7Mqeh7IUQngi9TCcFhp+G+glnpeHWt79ZanwQpRdVxVLiwTWUJXYpy9uN8P9PNF'
        'e5Taoa1VS8INxcoz+T3jKt1a8syL45egYkvNTHt0e/Ho9sHFsr9l1YtsyUop7MEKSm3RDagTr2BFtoCr4o+YmOX1ZAayBauWo9lK'
        'QU5AkjNwaBzFig1Kccuqm3ogcrPhftFNmo3sXE1W7cCUk9WjbJox9vr57J27K1gdDFI5nyp1kIqGB9mamAfYdtSWQ5ksjAxq1vLI'
        'AWJHI9ZhnciSfTLdyGr7RpQlnHKSDBttuyYGJfN7sCJeHbRcWyvLEYrs7sI9GeqvJiu5lIecoMiZRpb67bdvP7ygVPVhdThpimXT'
        '2i6sRkHdVvItu9qya7GBc1VI0dkQWvKNppjwX5L301HIYJGjyTkP+zs3MdQy9OuwwisXTeegIZrCNy+Xs24khQei/O7NSn5fznG6'
        'aqDENB5xl1BZDs1bapm08P66LwP7pB3cpoGbprA67LiSlVnaT80KG9CLdSU0FGhIRHI+G9ZN3VZkDZoelbKMgZTb/Yw2zgurZcuD'
        'FeH91dPJZtoObTHQnE3YVsWEkILYvnrBSpUjvICSk9CeDuxbViSWsMrglH21CCtyTnKkaeqsOsF6EM+74cm8ja3HjcNp6/ZmiOHF'
        '2GaUUlbPUrvj1EjphwCnEAjqW1b3TqawsmplIIsR0mw9Sa9evYI+KGSfzStA9rzLwA4rHLATmo9vLWCFs8CKM92ymkY6uO6sehSG'
        'b91dvX1/8+jW4vHd1esXi3U/uVgNpJ3OO/+aFTRgRWMBK1pPWDUCsVKWKuY/Z5NP9Ku7lEp+V8ygpnAu7O0Q2GFFuJasLqaNjl09'
        '6fq/ltXRKH14Onl8uXzz9gG4JKvVuIlJUBfzNqzGDQdWA1/bsqI2nHUCWFF0v3Fr0Y4dov3uzRtywsxVzq+yuXmiQ0arFAnst6ZN'
        'WHVcrRs9y6phKrAiPsOKzAFWSAtWUlq35q3Xzqavns/F/JB5R7JCVLBCVLBaNBzaUJLYrqf2XXU9FKwI77DaufFlWOV2b8qJKFf5'
        'RTuYTfWpPTwcPDgeb1n1SAwyVh3aL0Gp+ktWkU7MpzoGF6yQ1mHH27J69XwGqOOxcMBRbFH7wOpwEMGqH1mSFQJ+fGcJq2knjFxx'
        'V3S5kLvKueiWVa1cuLfs0AgKVijhE1Zn/eC8H0hWfinXyTqpcEBYiVEwPLHjIa15YkpW9zYDyYpqGlaAGkUmrB4eD2E17wRbVvdP'
        'JkjrGVbXoEOmWgqyjJ1G8GzenqfOMNC7ripZXQzCLatpZMBKIpKsjrONX2U1Oxw3JSvgjFNnyyohq4+sUcMhU5WsZFO4ZZW/8gsp'
        '0xQGWcZ+PmkMybpdTbKaxsaW1Sq1n2G1bthijkdmT7MC1D30eTQ8mTQkq9NhDKtRYsNq3A5gdXk4hBVuCCvCeyuyS/k90UV645Wr'
        'DKqb+L6pdWKXYAWrpll9hhUQJKujtjfM8slJNgwNq8MMGqwO2x4fA9QzrPBBWM2a7tmkuWW1GqWwIm2A1de+ciFZaUqpmNu74qxa'
        'oQMrz1BhRSO4ZXU8TFbdcBgLwVyME8lqmfWrzxJz03JhJXEBaiPmzOiAmiR2x6jC6jQTFazW3WDZCWhSt6zmvQhWpA2Slah0+jFu'
        'CKv87pX2QddQQ1uXgX2bMEybpE+J6GbvhQ/WPVjdmqRICFZIS7Iidf+ElcuPGJSkSVadQB8EhmTVctWmqwWGAq5h0zsaJptp64+/'
        '+fCD9+/D6uSgN2gFpqbs7VzpBbKqxXzsGpNQuJtsBBHVQSf816zksJdkNU3MLatNZheTxgGcM1b92IKGZHU8SmHVDfSgXoZVN7Yl'
        'q4tl72tvnv+nd+68+9qxZCXvb7rirGrlomRFYB9HBqKC1eEwOZ02sVdJujb981EsscwTC1yw2rSfSEuCkqwkrlurPjTwstRWEeqW'
        'FdKC1XKQTJreltVX7q1vHY5mg1TMdb/aIxSl3B7VK6zO++EzrM4XHckKgxUhXbLCFqklWRHN1r1Q2v2jkbTLdR9Qia0ue6Fk1bBr'
        '1H1Pszrsxx+8f+8PXj+G1YPzea/pF658f3s5L2pnog2sUI5kdfdodL7owmo1iM8yXJcULBmro364bjkYuFatjFU/+lVcwy2rpiM6'
        'Aweh0fJ0WGF6brft67Ail3uGlV696ktMoytLU9ZNmyyUtg9Ws4zV3c3woB83vTpNG6weXcyJ0q+dTASrtitxSVZPcGXE7h4OccD1'
        'pCluPwnNSSfYsho2XFjZxb2v3NvwAVh97717b93fnK/6kpVaKX7pyr+eZgWo+6fTLatRy5+3/YPU/cqd5b2jEazOxqlglbV9sDqf'
        'tX7Jqh/B6tGdFSjOln2CFawWnaDjC1BYaFSPZm1Y3T2ZvPvq0bffufO1Ny9Ol/3lqLEYNdqJc/VZddza0SCSrF6/WMBq2g1hNWp6'
        'sDpZdJ5mdX8zkNLaiFmRrphTNGttWVEMwuqNyyWsNtP2atTANuNmL7axUFfg9v4bp++/cXY4a8Pq/UdnsDpfD34PWJ0d9Kjdbq37'
        'T7OS0oLVrXn7cNLcSuvhrQWsHt8/lKwgAKjLw1EntCQoRAWrs1VfsvrmW7efZtVv+teI1Ru3D55mdbro3sPpDnpI6wHNejdaDBLJ'
        'CvcEFHaW4cIAhZAwyWo+SMiaTpe9Late4gAKB7zWrMg/37y9+LWsHpxOYYUeXjufgwtWb5zPYEW2KUGdfYLraVZHiy4bsDpadO4c'
        'T4jeiIqvSFHd2gy/9fYlgf2910++/vgWrHDb68jqYj2QrN559ejRrQWskNadzZCzBdf9w+HlshtqJU4caZ09hUuygtLZaiBZAere'
        'yRRQGKKSDjhouGfzzr2j4dOs7p3OrgUrrVL8taxwIli9c38jWWH3Vr1nWNHM8Ulpq2EKonE3oo17cCZ6RyWrw2kLk6KatP2nWdEI'
        'vvfwdMuqGdlXn9Wtg+4zrB7f28AKUBhZU9tRpbTA9QyrLa4tK0Cdr7Le0bMZ1k0cTMwSceuwurMZLPvx66fjd+6tCVbfeffuVx+d'
        'XRdWavlXWJEajdvB/eOxFBV2MW2AS7KapxY/PsNK4oLVoCnukpCgSLTuHQ4lq35sAwobt7wtq/snE5x6y+q1WwfXgtWr57PfxOp0'
        'lEhWYlgh1LtODXuG1bjhrscNzn3ei2F1ez0AlGR1L+un6rhayxOgpm0f+02sWrFTyl/phzRVCrlnWC2H6TOsWo4qpnxY1YapxHpF'
        'ssKgNM4S8i0rDFYiuB0O5y1XgpKsBqkDqFXLlazODrpTtw6rx2RuGatGaFXLV/05C/8mq56nIq3UqIBLskqMSlgvSVAYoDC+KKWF'
        'U8+aHqwkKGwUGRig+n79aVY9XYHV4awjWRWu/ALvj+4sX7uYP8Nq1QsBtWWFIa1pbGKoC1bSOoGObVndWfUxyWoh1hywsXFmW1bY'
        'yaTxDKv1pAWr+tXualCKOcnqD796/87RSLIC1JaVBCVZTfz6wKphT7PqhibGtw56ESZZAUqyGj9l/yarKy6qwKqHllZXxLxNS61g'
        'mlgUi8ixLwYLsn5dTEyj2r1ZLecL/HPjlfzerq1VfnvfhdhnpaiIJ6gWa+WCppQsrYr5poaZqlj0DrPrVXbLPuvV0lXuFzVqlXkv'
        'hRVNe+Ia0mLPlJ2lrl7Dtqz0ahlOnL5eq+ze/LK4p/s39zgZtTK4uBD7OzckLk2gK5ULOX6P8ePOjVfkOkVFserOPgdzxR9IEdo6'
        'oGJHN9UKoNqBsezGnCPW8MUMLUChsZpYza8MHKywL8Y9f4sGnHoVVnK1qEpB9CVWS3nJim2xh9wu2AtCV+KvvGO53ZvI9SrjUop5'
        'KOEvW1ZQ6kQuxllUson6UEIbnqFyvuIc9/dwUvM3PymvHbnd2BVPPasUzZpYYA19stvYNVqBjeF3gJKKlZQKYm2Z3b2dG1d2bq18'
        'EYCK+X2uqeh7z+0JFQnxiIMXKwMU9nN7O8QZiFXEVGERsczfeodaMb+nVgpioSpNrC2AzPiu1CoXhYwOJpVivpzPYfL3OjpUSoGt'
        'f+nKv0BkqBUR0HdvciIYAQTLIvCTeMLfcD0EVv10694gHvZGoCtll0Aa9OSPXA7+Oyjhkvida9Q05Rr0t29xgYi4xDviyUbrBCtM'
        'ICoScESj9lxzqtknxPL7u+wKMbFn6AlQ5UItezSMBHWNKP1yTCe/z+lkJ4W6bmZRXUz18UyN0+Gv/76hFnYILjhLVhJUObcLq+v7'
        '2FlXF8sSNjyxkn9TPLOjNO+GYmVIsUa9eLqBUtx/rrmvviGWEGGHnl6ZtHx2FTt1q1bqxbZ8gGOtlHPr1/K5hJyLJxZJE88mztZj'
        'LF3M2052RuJJXlWxaqWtPUcZYmVr5DY93TcUuc/TScvRyuxQVwp4Hx79XDu8SroSy9oHQgzVBXVLtch5iWdqZA+/rmS31TzXDp16'
        'RUjLEs8hYodiWePs0RuRrYlb4Qp7n+HyaC+63jGrqavhMhfzDpIAltQAZ5e4dWILjvNc66CKld5dDTvP9Cnv2clEVWSHYmnl4jV+'
        'qnhgcnbiESSjhhvbwhmxQerKtX+fd8FYvYomxRN22CExKltmv0bs6sWOeGSVQhVwjR8Mmi3BXbXUknxKy6IT8uOTBWm18r/j4fKw'
        'gjY7xNg4Gol1fvBuEdV15dqtNvD0qxOKModQfH89NLOFoGkB8ZSmZ5Ry4unDplp+3h02s5vI2KFkLtqI7MYuuWjt8+7w6ryG2ZjL'
        'apBcLLqBrmRumC11KFYZUqXjPFcAHKVutpxREFtiMfbIqgaGshmmJA/8Va6cf01ZtXydU+O8zFo5ytpEModB4mRrktfkrZHPtUMC'
        '+yCxG65YH4ztyBRrt3q6cEzRPtYr1evZFIrHKgVGXwRhNbFrWBaKFUxs1MXdgs+VaafZDsk+shuEa0JahiKfGkbbSiijKbkKzzj7'
        'd7w4tV5skQe1M3X1xbbZ9HUMf8HE4wOeh5W4N9/X0RL7QV0YG63AwBBVKNR7LcucxNE4r1ag97OTwmDVi4QJT9TEsuqUOZ8+e0Sl'
        'tHlCqGLZQwfrRaJnvhOacofZzZV59Rqyks9LJflJHLWdXXqS0idP1dHEM0/FWrgUvJX8p8yykA1eJtZjz4ixQ97ZIVELUNkqxOJO'
        'cD6gX7d+BnlvcpKZeIKJp/MjoZ6zQwCyuRcPjyjuf0olZFjEYoYIDC21M1ZptnNYPckfxJIy4kEn14tVlOmKGC60hPu4dd5hRTVd'
        'VwriQZOlXLbg86fNiMJsVyJXN2s4snhqoW+wW7lD8dgLucPscUvXi5UscoOsTReSyB4StH3qEIYAiMM1MTT2qViRlsuWjqvABjvE'
        '+2hS5XINuJ5Y7iNbIOXasUqFigxSqWHqjpvuuOF1syfFiPLQqomV8JVCLetA/pQP9GFvzWwBfGzS9CYNb9xw26F4gGP2ZIoyxaB8'
        'OIh13VL30BQqgkzsaFH23D3hL5yUVtFF+Sae2yKWxNcqhK9Ps0O+m4lKi+UTlCzxKCWqgGz9EIFdzR5AI55SZ6lfevn6Xb/+P0a/'
        'M5U='
    )),
}

# Keep the navigation footprint synchronized when the approved counter mesh is replaced.
catalog = (ROOT / 'source/gamemap/RoomObjectBounds.h').read_text(encoding='utf-8')
counter_row = re.search(r'\{"TavernCounter",\s*([^}]+)\}', catalog)
assert counter_row, 'TavernCounter navigation bounds missing'
counter_bounds = tuple(float(value.strip().removesuffix('f')) for value in counter_row[1].split(','))
counter_min, counter_max = MESHES['TavernCounter'][2:4]
assert len(counter_bounds) == 4 and all(abs(actual - expected) <= 0.00002 for actual, expected in
                                       zip(counter_bounds, (*counter_min[:2], *counter_max[:2]))), \
    ('TavernCounter navigation bounds differ from the approved mesh', counter_bounds)


# Deserialize the actual game file with a bounded native converter invocation.
def deserialize(name, directory):
    converter = os.environ.get('OGRE_XML_CONVERTER', 'OgreXMLConverter')
    target = directory / (name + '.xml')
    subprocess.run([converter, '-q', '-log', str(target) + '.log',
                    str(room_file('models/' + name)), str(target)],
                   stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                   stderr=subprocess.PIPE, timeout=120, check=True)
    return target


# Stream large meshes and reject invalid geometry, UVs, tangents or skin weights.
def check_mesh(name, path):
    vertices, triangles, wanted_min, wanted_max, wanted_materials = MESHES[name]
    totals = array('f', [0.0]) * vertices
    counts = {tag: 0 for tag in ('position', 'normal', 'tangent', 'texcoord', 'face')}
    minimum = [math.inf] * 3
    maximum = [-math.inf] * 3
    materials = set()
    skeleton = None
    material = None
    points, uvs, faces = [], [], {}
    for event, element in ET.iterparse(path, events=('start', 'end')):
        tag = element.tag
        if event == 'start':
            if tag == 'sharedgeometry':
                assert int(element.get('vertexcount')) == vertices, name
            elif tag == 'submesh':
                material = element.get('material')
                materials.add(material)
                faces.setdefault(material, [])
            continue
        if tag in ('position', 'normal', 'tangent'):
            value = [float(element.get(axis)) for axis in 'xyz']
            assert all(math.isfinite(v) for v in value), (name, tag)
            if tag == 'position':
                minimum = [min(a, b) for a, b in zip(minimum, value)]
                maximum = [max(a, b) for a, b in zip(maximum, value)]
                points.append(value)
            elif tag == 'normal':
                assert abs(math.sqrt(sum(v * v for v in value)) - 1.0) < 0.005, name
            else:
                parity = float(element.get('w', '0'))
                assert abs(abs(parity) - 1.0) < 0.001, (name, 'tangent parity')
        elif tag == 'texcoord':
            assert all(-0.0001 <= float(element.get(axis)) <= 1.0001
                       for axis in ('u', 'v')), (name, 'atlas UV')
            uvs.append((float(element.get('u')), float(element.get('v'))))
        elif tag == 'face':
            triangle = tuple(int(element.get(axis)) for axis in ('v1', 'v2', 'v3'))
            assert all(0 <= index < vertices for index in triangle), (name, 'index')
            faces[material].append(triangle)
        elif tag == 'vertexboneassignment':
            index = int(element.get('vertexindex'))
            bone = int(element.get('boneindex'))
            weight = float(element.get('weight'))
            assert 0 <= index < vertices and 0 <= bone < 15, name
            assert math.isfinite(weight) and 0.0 < weight <= 1.0, name
            totals[index] += weight
        elif tag == 'skeletonlink':
            skeleton = element.get('name')
        if tag in counts:
            counts[tag] += 1
        element.clear()
    assert counts == dict(position=vertices, normal=vertices, tangent=vertices,
                          texcoord=vertices, face=triangles), (name, counts)
    assert materials == wanted_materials, (name, materials)
    assert all(abs(a - b) < 0.00002 for a, b in zip(minimum, wanted_min)), name
    assert all(abs(a - b) < 0.00002 for a, b in zip(maximum, wanted_max)), name
    if name == 'Innkeeper':
        assert skeleton == 'Innkeeper.skeleton'
        assert all(abs(value - 1.0) < 0.001 for value in totals), 'Unweighted skin vertex'
    else:
        assert skeleton is None and not any(totals), 'The counter must remain static'
    return {'points': np.array(points, dtype=np.float64), 'uvs': np.array(uvs, dtype=np.float64), 'faces': faces}


# Triangle budget of the owner decision of 2026-11-17: total in range, fixed counts per material, delivered file unchanged.
def check_innkeeper_budget(mesh):
    counts = {material: len(triangles) for material, triangles in mesh['faces'].items()}
    assert counts == INNKEEPER_TRIANGLES, ('innkeeper triangles per material', counts)
    total = sum(counts.values())
    assert INNKEEPER_BUDGET[0] <= total <= INNKEEPER_BUDGET[1], ('innkeeper outside the triangle budget', total)
    with (room_file('models/Innkeeper.mesh')).open('rb') as stream:
        digest = hashlib.sha256(stream.read()).hexdigest()
    assert digest == INNKEEPER_SHA256, 'models/Innkeeper.mesh differs from the reviewed export'


# Canonical key of a triangle given by three corner positions (the same for every rotation of the corner order).
def triangle_key(corners):
    first = corners.index(min(corners))
    return tuple(corners[first:] + corners[:first])


# The inside of hood, sleeves and apron stays drawn with back faces culled: most cloth triangles have a twin on the same
# three vertex positions with the opposite winding. Returns the measured fraction.
def check_innkeeper_inside(mesh):
    points = [tuple(point) for point in np.round(mesh['points'], 6).tolist()]
    cloth = [t for material in INNKEEPER_CLOTH for t in mesh['faces'][material]]
    keys = set(triangle_key([points[a], points[b], points[c]]) for a, b, c in cloth)
    twins = sum(triangle_key([points[a], points[c], points[b]]) in keys for a, b, c in cloth)
    fraction = twins / max(len(cloth), 1)
    assert fraction >= INNKEEPER_MIN_REVERSED, ('the inside of the innkeeper cloth is not drawn', fraction)
    return fraction


# Colour of every triangle: its material's colour atlas at the triangle's UV centre (Ogre v runs downwards).
def triangle_colours(mesh):
    script = room_file('materials/scripts/TavernObjects.material').read_text(encoding='utf-8')
    colours, triangles = [], []
    for material in sorted(mesh['faces']):
        block = re.search(r'^material ' + material + r'\s*\n\{.*?^}', script, re.M | re.S).group()
        texture = re.search(r'texture\s+(\S+Color\.png)', block).group(1)
        image = np.asarray(Image.open(room_file('materials/textures/tavern/' + texture)).convert('RGB'), dtype=np.float64)
        tri = np.array(mesh['faces'][material], dtype=np.int64)
        uv = mesh['uvs'][tri].mean(1)
        h, w = image.shape[:2]
        colours.append(image[np.clip((uv[:, 1] * h).astype(int), 0, h - 1), np.clip((uv[:, 0] * w).astype(int), 0, w - 1)])
        triangles.append(tri)
    return np.concatenate(triangles), np.concatenate(colours)


# Small depth-buffered orthographic render of the bind pose: flat atlas colour times a two-sided Lambert light, back
# faces culled (counter-clockwise front faces, as the game draws them).
def render_view(points, triangles, colours, view):
    forward, up, low, high = VIEWS[view]
    forward = np.array(forward) / np.linalg.norm(forward)
    up = np.array(up) / np.linalg.norm(up)
    right = np.cross(forward, up)
    width = int(round(2 * RENDER_HALF_WIDTH / RENDER_PIXEL))
    height = int(round((high - low) / RENDER_PIXEL))
    sx = (points @ right + RENDER_HALF_WIDTH) / RENDER_PIXEL
    sy = (high - points @ up) / RENDER_PIXEL
    depth_of = points @ forward
    light = np.array(RENDER_LIGHT) / np.linalg.norm(RENDER_LIGHT)
    image = np.zeros((height, width, 3))
    depth = np.full((height, width), np.inf)
    a, b, c = points[triangles[:, 0]], points[triangles[:, 1]], points[triangles[:, 2]]
    normal = np.cross(b - a, c - a)
    normal /= np.maximum(np.linalg.norm(normal, axis=1), 1e-12)[:, None]
    shade = RENDER_AMBIENT + (1 - RENDER_AMBIENT) * np.abs(normal @ light)
    facing = normal @ forward < 0
    for k, (i, j, l) in enumerate(triangles):
        if not facing[k]:
            continue
        xs = (sx[i], sx[j], sx[l])
        ys = (sy[i], sy[j], sy[l])
        x0, x1 = max(int(math.floor(min(xs))), 0), min(int(math.ceil(max(xs))), width - 1)
        y0, y1 = max(int(math.floor(min(ys))), 0), min(int(math.ceil(max(ys))), height - 1)
        if x0 > x1 or y0 > y1:
            continue
        area = (xs[1] - xs[0]) * (ys[2] - ys[0]) - (xs[2] - xs[0]) * (ys[1] - ys[0])
        if abs(area) < 1e-12:
            continue
        gx, gy = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
        w1 = ((gx - xs[0]) * (ys[2] - ys[0]) - (xs[2] - xs[0]) * (gy - ys[0])) / area
        w2 = ((xs[1] - xs[0]) * (gy - ys[0]) - (gx - xs[0]) * (ys[1] - ys[0])) / area
        w0 = 1 - w1 - w2
        inside = (w0 >= 0) & (w1 >= 0) & (w2 >= 0)
        if not inside.any():
            continue
        z = w0 * depth_of[i] + w1 * depth_of[j] + w2 * depth_of[l]
        block = depth[y0:y1 + 1, x0:x1 + 1]
        nearer = inside & (z < block)
        block[nearer] = z[nearer]
        image[y0:y1 + 1, x0:x1 + 1][nearer] = colours[k] * shade[k]
    return np.clip(image, 0, 255).astype(np.uint8)


# Render comparison (owner decision on the triangle budget): the reduced innkeeper seen from the game camera and from
# the front differs from the reviewed render before the reduction by at most RENDER_MAX_MEAN_DIFFERENCE (mean absolute
# difference per channel, 0..255) and covers the same silhouette (intersection over union). Returns the measured values.
def check_innkeeper_render(mesh):
    triangles, colours = triangle_colours(mesh)
    measured = {}
    assert set(RENDER_REFERENCE) == set(VIEWS), 'a reference render is missing'
    for view, (shape, encoded) in RENDER_REFERENCE.items():
        reference = np.frombuffer(zlib.decompress(base64.b64decode(''.join(encoded))), dtype=np.uint8).reshape(shape)
        image = render_view(mesh['points'], triangles, colours, view)
        assert image.shape == reference.shape, (view, image.shape)
        difference = np.abs(image.astype(np.float64) - reference).mean()
        assert difference <= RENDER_MAX_MEAN_DIFFERENCE, ('the reduced innkeeper looks different', view, difference)
        a, b = image.any(-1), reference.any(-1)
        overlap = (a & b).sum() / max((a | b).sum(), 1)
        assert overlap >= RENDER_MIN_SILHOUETTE_OVERLAP, ('the reduced innkeeper has another silhouette', view, overlap)
        measured[view] = (round(float(difference), 2), round(float(overlap), 3))
    return measured


# Verify material references, atlas dimensions and the licensing of every new texture.
def check_atlases():
    script = room_file('materials/scripts/TavernObjects.material').read_text(encoding='utf-8')
    credits = room_packages.credits_text(ROOT)
    for material, size in ATLASES.items():
        block = re.search(r'^material ' + material + r'\s*\n\{.*?^}', script, re.M | re.S)
        assert block and 'normal_map tangent_space' in block.group(), material
        for kind in ('Color', 'Normal'):
            filename = material + 'Approved' + kind + '.png'
            relative = 'materials/textures/tavern/' + filename
            assert 'texture ' + filename in block.group(), filename
            with room_file(relative).open('rb') as stream:
                header = stream.read(33)
            assert header[:8] == b'\x89PNG\r\n\x1a\n', filename
            assert struct.unpack('>II', header[16:24]) == (size, size), filename
            assert relative in credits, filename


# Keep navigation at the approved counter's measured footprint after model replacements.
def check_counter_navigation_bounds():
    catalog = (ROOT / 'source/gamemap/RoomObjectBounds.h').read_text()
    row = re.search(r'\{"TavernCounter",\s*([^}]+)\}', catalog)
    assert row, 'TavernCounter missing from navigation catalog'
    actual = tuple(float(value.strip().removesuffix('f')) for value in row[1].split(','))
    minimum, maximum = MESHES['TavernCounter'][2:4]
    assert actual == (minimum[0], minimum[1], maximum[0], maximum[1]), \
        ('TavernCounter navigation must match the approved mesh', actual)


# Exercise the native assets, navigation footprint and existing innkeeper animation contracts.
def main():
    check_counter_navigation_bounds()
    if not ROOM_ASSETS:
        print('check_tavern_approved_models: navigation bounds ok (tavern room package not present: its meshes, rig and '
              'atlases not checked)')
        return
    check_atlases()
    started = time.perf_counter()
    with tempfile.TemporaryDirectory(prefix='tavern-assets-') as temporary:
        directory = Path(temporary)
        converted = {name: deserialize(name + '.mesh', directory) for name in MESHES}
        prepared = time.perf_counter()
        print('ODP_TEST_PHASE ' + json.dumps({'name': 'setup', 'seconds': prepared - started}))
        meshes = {name: check_mesh(name, path) for name, path in converted.items()}
        check_innkeeper_budget(meshes['Innkeeper'])
        inside = check_innkeeper_inside(meshes['Innkeeper'])
        look = check_innkeeper_render(meshes['Innkeeper'])
        skeleton = ET.parse(deserialize('Innkeeper.skeleton', directory)).getroot()
        assert len(skeleton.findall('./bones/bone')) == 15
        clips = {a.get('name'): float(a.get('length'))
                 for a in skeleton.findall('./animations/animation')}
        assert clips == CLIPS, clips
        for animation in skeleton.findall('./animations/animation'):
            assert animation.findall('./tracks/track/keyframes/keyframe'), animation.get('name')
        print('ODP_TEST_PHASE ' + json.dumps({'name': 'validation', 'seconds': time.perf_counter() - prepared}))
    print('check_tavern_approved_models: ok (2 native meshes, 15 bones, 3 clips, 12 atlases; innkeeper %d triangles, '
          'cloth inside %.3f, render difference/overlap %s)' % (sum(INNKEEPER_TRIANGLES.values()), inside, look))


if __name__ == '__main__':
    main()
