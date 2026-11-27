#!/usr/bin/env python3
"""Check the approved tavern exports, their skinning and their runtime atlases.

Owner decision of 2026-11-17 on the triangle budget (INGAME-QS-10 A1c): the innkeeper went from 248891 to 33291
triangles with no visible change from the game camera; his cloth was two layers, the inner one a reversed copy of the
outer one. Since CS10a (2026-11-26) the innkeeper is the approved Meshy figure of the content package creatures: one
closed surface with one material (InnkeeperMeshy, one colour texture) on the shared 24-bone humanoid rig, so there are
no cloth layers to keep and no tangents. Checked here on the delivered file:
  budget        INNKEEPER_BUDGET triangles, the count of the approved export fixed, the delivered file unchanged
  look          a small software render of the bind pose from the game camera and from the front (flat texture
                colour, two-sided Lambert light, back faces culled like the game) differs from the stored render of the
                approved figure by a mean of at most RENDER_MAX_MEAN_DIFFERENCE per channel and covers its silhouette
                by at least RENDER_MIN_SILHOUETTE_OVERLAP (intersection over union)

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
    'Innkeeper': (7817, 9993,
                  (-0.419514, -0.105307, 0.0),
                  (0.419514, 0.105307, 0.785947),
                  {'InnkeeperMeshy'}),
    'TavernCounter': (53071, 43424,
                     (-0.52, -0.338, 0.0),
                     (0.520001, 0.0549586, 0.412484),
                     {'TavernCounterWood', 'TavernRail', 'TavernSign'}),
}
ATLASES = {'TavernSkin': 2048, 'TavernHood': 2048, 'TavernCloth': 2048,
           'TavernCounterWood': 2048, 'TavernRail': 1024, 'TavernSign': 512}
CLIPS = {'Idle': 4.0, 'Pour': 5.0, 'Cheer': 2.0}
# Triangle budget of the innkeeper and the approved export of CS10a (Meshy smart topology, about 10000 triangles; the
# owner budget of 2026-11-17 for the former two-layer figure was 20000 to 35000)
INNKEEPER_BUDGET = (9000, 35000)
INNKEEPER_TRIANGLES = {'InnkeeperMeshy': 9993}
INNKEEPER_SHA256 = 'd2d8f922b1bbfacb7f2cbe9b0613d7379713d9e092f1a250fa62793f4d184f7a'
INNKEEPER_BONES = 24              # shared Meshy humanoid rig (the former rig had 15 bones)
# Vertices with a tangent per mesh: the counter is normal mapped, the Meshy innkeeper has no tangents
TANGENTS = {'Innkeeper': 0, 'TavernCounter': 53071}
# Material script and texture folder of the materials whose colour texture the render reads
FIGURE_MATERIALS = {'InnkeeperMeshy': ('materials/scripts/Creatures/InnkeeperMeshy.material', 'materials/textures/')}
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
RENDER_REFERENCE = {  # zlib + base64 of the uint8 render of the approved CS10a innkeeper (Meshy figure, rendered by
    # render_view from the delivered mesh and InnkeeperMeshy.png, 2026-11-26). Before CS10a: the render of the former
    # innkeeper before the reduction (reviewed 2026-11-17, rendered again with the atlases of INGAME-QS-11 K8; owner
    # decision 2026-11-18 "Neues Referenzbild, Grenze 4,0"; measured game 1.93, front 2.91)
    'game': ((150, 100, 3), (
        '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'
        '4hGP/1fjPwGd2qUY'
    )),
    'front': ((137, 100, 3), (
        'eNrt3emTHOWd4HFezBihvuq+MrMqj6rMuu+zq7qrb7X6ktQtiRaNJBAgEMshyZgBAw7GJzA23rH3hV94dmNjdyJ2X+z/uN+sn5QuqgED'
        'o5hQCXV8g5BBblV/lJWV+eSTTz7zzNOvp19Pv55+Pf16+vX063H5ahVz7VIhk0pamvpU45u+uuXCWqMM1HqzVDRTBcswVGWpmH4qM/GF'
        'UrNY6FXytXy2Vy4YSlyLx3K65uiprJ586jP+tVQrNfPOUq1QyznnurVBJTeoFexkIpWI5XXtqY/3Vcum2Zyw6tfyK83S4bC702usNcs1'
        'xzRVxVQSyUjgqZJ85SyjkrWpVUgfDbvDWgGrK2uLtazhWqnKwtzcUyW+Umw2SgKuYaN4MGgc9SuHy83DYed4rfviWrNipUL++aBvPhZ6'
        'umk9k05pFduKhvwpJeKk4i8N8lUr2c+njweVVCQYDS6klGgk4IPrqRVW7VIupUYNJfA/PhrG/Gf3eu1MPBaeP6OHnjUVX8A3B5S7aQV9'
        'P2ao1UrG0BQ7qebTycVKfr1i39paOeovOkqin7PTSpSCvAcX5nzzc9HAwo/Z6sJiqeoYcd5jC7Mr9WI9ndwftI1opGboWV3NJMLnm0XH'
        'UN13aDSg/Ii3q3zGKKfd40ygzFR8sZQ5WKxdGXavrC0t10vNXKZgaNkU78ZANOzu2OOB+ZD/R8pVsFLdgnsKEwkHGuXsTq98vNmz1VjR'
        'UDPsvmKh90720lqEffvM2efcN2w1E/9Rvg1z6VTWSCoRf8g3pyrRbi1/c2d493i7oCdyqVjJUHLJGBtVp8jBe3R+bobfNj/7HNuVqUR+'
        'bFbtYnqr4fCLkH9O12KVXGa9U1qtZ9cbztZS53hn7eJKO61GiulkLBK0dHV+9mzZjLVsLRkL/tigZE9lJdkbLRTslJFS2H4qWbNRyZsp'
        'pZy1CraRiIZsQ41HQ9HQAlYpJcz/BSvrx7RprVbtqp1qF1CJJCIBLRboldJqIsI+3NASGV3VEpG0oVm6Fgr6ajkzMD+TSoQzqQRQRT32'
        'o9q01uoOJWIht5HVYjlTNNVwyJdSY5HAfNg3FwoshEN+NRKoWKpnZSbjhhozY4HPPnjr2vbaJy+fPEksm43cg19UHWrlzE4xU8sZVHb0'
        'bsHIpmK2oeiJUL9sV9KarkRigXkzEfLNz0T8c+2cEQ8ucITVzOnDis0hq65Gf333Vazu7G3/60d331hZuntw7vP7b9h6fOpwqlmrX3Eu'
        'LteH9Vy7YFHF1g96/OuUbWgMHYhVwUyIVUaLilU1kxSr+ZnnUomIWDXs5LhVh319PPLX33306d3b//7HX/733/38VzeOPh6u/PsXnxhK'
        'pGKnqlmT+CMe9/G6qkPnOkWGVtjJNEuOY/HirUEpTUXbwKqcVuFaLlvZZJhWq1bZiLdz+notY6nRS0u1g8VKxD/PYVXZUBqZpH9+ZqWe'
        '5f/uWlXT7Rzvwshv791+ftjH6nfv3flke+NfTi5f39/EqmSpzbxVtnUCmZYqzn8yQjdvTvybS8stU43xi34lp8QihYyB0mqDQd8EH2G2'
        'rgK1Us9V0ypWwoWVZGpxsUorwZwWSCvhQiqGVTEVB4qMWLDlpLAioGhYsvolw4z7KJuM/PXzj28O+v/ry3/+w8d3f//C5f/3+4//7dP7'
        'QBXTGlb1nFteT2BlJRVCLGMkl2v51Xq+4phW6isDrfVs+mip/sNktno16eVzvW7Jpu1WYaNZMJWYY6RWajmgdDW22iytNgr8T16AKFGz'
        'kAGK6rl0Pp06Xqu1i5lxK94dFUfHytYTqZhvqZDSY4F6RsXqoFei3d4Dq71etZFOEFaltNay1aYVXcwlsfrFO698cOUQq7/85gOs/u2n'
        'b2AFVM1JYpVJKViFAz4O/sVKuFJKnHK6WnWspqPv9fko1nidOSt1vlMeVOzrq80LS439QVNaLE9uk+daBTroV7Y7Jdrplq+ud6VB0aR+'
        '0WrmTKzyhsLfyFo9zzfR1USn5NByNU2NrEFLlQxWvB5egK7EPSvhEiixooIRp/VSqm4leA8OiyZKUiYR5LATKwnGjXp2uWQART9/5cVf'
        'v3/nT/ff/PMn7/7l1+9/OBxi9deHVqmof9yqV3ZsI0mdvNVx354p6pRyZa6oxSNZQ8tbOlZ84tQdnTZbhasrDTrXzG73qufbJbqwWB6W'
        'ra26vb9Yob3F0uFSBSjitIuw2oGuUxKrYS2biIbXGoX1RqFXsgtpnV03tQrWuJX83emjsga7JlOs+A8CJVZ1d7cTGFZMgkKLLnTyetPd'
        'umysODi/uuQqbdTS/Nd+geOFOYEqJsPvXX8eq7/ceQWre69c+/Xu9v/+7Od//uQeUMS+jj18NOgbtxKoRs6s2SlKqXEtFnJfpBrvVXKW'
        'lhAroMQKKLE6XK7TaqdyYbm93cxVLKXtpIhXSOsVY6Nq0W6nULUSxLteT0Srtq4rMTOptLNGzTGwks+41ii4gCLb4MMuxcvoFizPCij5'
        'uyasgJIEql1IY5WMh6hkJNZrzqBoHfSKW63sSo1RmblEeB4iWrQTXTvxs5vH/3z/Nlb/54+fYvXbW8df3nv9Dx++wx9HYpWMh+ECyrMC'
        'ijg+IUbMsOLEoZqBTjeU6HIlU9DjdL6V2+sUpaWC/qCKTetVEyvhEiixAor4DVjlTG1kxamugtVSOYNVr2C4n0oFtmpjpZom9mY0YbXX'
        'ywuUZ8WxeitniNVOK9vKGwSXWLmHHGZMrIZVoOapmjPFKub7B3ZfWF3dXv3i7mv/97/+8pO3XnlzffhPr5x89v5bp634myJLi+Y4Ex8F'
        'FKdUjJj552cZNLO1mFgVLU2gaLNdFqutesazAmq9mk4rISPmJ4EigRIrwsrWohVLw6qeNbGqO5y6hcat2G+KVSenN7Ju8spnn/uJocU9'
        'q4KVFCsaDPr1dJy2B03hYv8mXINy5tKwEQs+gBKr/X5lt1+mLz+6J1b/8/OPsTrWnZv75+ByoQLzHIwBNWZlYCVc/EuxCizMzs6cnbBS'
        'wj7PSsJKyqohKlsJrITLSoRKltawU1LFTPRySeIjPsG5RiyoRoNKPMqQiFjJppWIBAkrAkqs/AvzWjRAnpVAiZVwYZXwz5ZT4ejCWdm6'
        'ipmkx3VhUPagiC3K66W11TdODsXqXz+561mdX+l/ixXD9VwPCvvn2ajEip1gKhbEKhTwGYkwpwdGIpjX4+zzOKsi9v9pJUJAlYwoVoyB'
        'SECJFUrUyKiSZ8XRta2z/bhnu/GwPxH28xLEipcRGA2JS55V0VQIrtNWhGXM9xMCKqsnsJJSSoiNqphOSXoimFbDjhrin2YigNWff/kz'
        'uP76mw8+/9mbHTt9tNp//6Vrn777GlahhdmFuRmCCyhSYiG5tCFWsZDPNzcjVgzgYxUPB9JqVA37gRIr4cJK6o72k/RgiDIZeVAqyoiH'
        'ZMTRDvP92Qmw6VpajF8899wZoIgPGq4awMVrkDwusTp75lmxYvxz1KTV1aUyu6z9jq2G57ASLqDcEuGCpYxb3VgvLhd0fn9GDYvVF++9'
        '+dv7t7/JSomG3B5CUdh9kQtixUArLzjj4of50djNsbGZHI+pUf6NVNbjNSsh7bWzk9fKLQWrUcwiUKTwCIohE7FifFIZs3I33XjQvzAn'
        '8TLGrcpGjDgrmbASrsjCP5T0KH36yr5059JQ+t1r+9K9q6vvHG/S6xeX7YRfC5xh0/rs+tFrxxfEqlVwPCs1tDBuxR6JfbikRAKElUCx'
        'FbFpYRVcmE1GA7xxsAIqm4xT1VKAot12/u8euvdyepXNj5kEIZ8RD/HN3a03uKCNhnyx4sWU9ehoQ5oVLn7DONeElcc1YcXO6qBpnQws'
        'oK7vLQvUF//l8gvb3XEroLqZeHjuTCbmE6uTleFbre6b25u7S90Vx/7N26+e7G6KlXB5UJx7CxQvlb0HL5W3hljxA3CtljP0qH9ODfts'
        'LdJykrTd/IFnkQzk4g+UWHH6xqeAu0Ng3CkSEC5JuGbOnvG5/3h29sw/8l8F6iHXpBUXAvnn9c0q3bu2Q5+9/YJY3T7cuDSs0Gan9PKF'
        'Nbaodjom29WfP3hzzXGwOiyXi6HIxfWlP/383rXdjWv7W+GFs1ixUbEJCZT38oCyk1FOxrHivRP2uxccGd/g8lDUHdD4z5iNk+Eigh7n'
        'gFIKLrCRnwFqwoqROlquZqRUInB7w5be3G1htdSyxeovH772+VvXxEqgPrp9fLVvSevtwh9/cf/V8+unrdiusKKCEeOTj893jjmlSlrx'
        'XjBcD/bSRuJxGJ8J+Wa57CJWouQlUL95dVeg3r52nu4eLWJFrx+tixUnLFc2Olj9/v7Lh8MKjVu9uLPxp7duYdUzDc+KfQX7H6CmbtCP'
        'bVv2GAxKjFfNqGIlXGLFpvXe9b3NXongEij6w7snbFSeFVCu1UfvXt9e/fK9O/duXL68tYLVO/3FNdPkcj5WUzqAzKH06LTjb2JAEWd5'
        'YiVQYvXf/uk1EjFRevd4iwRKEislPH/3xcOF2TO7veYL68vvnBx99PrNw60VdpbTO9jOR4xwkeMOiibFanexfOviGt3cWyLhEiviDfjy'
        'hVWB8qwu9ku0tVijYT2L1f2Xrtrx8LgVR8XTaxUL+YULKLGSxOrKWpOEiyDywkpaLKREacKKwyGsbu1trWYyWN3YXnOtwv6pvo7DADvD'
        'th4UF/7otNWvbh/97NrWB9f3JIjoaFCii92cQK01sjRutVwrPXlWJEoCRQJFKElYeVwe1AOrEZdYASXBdW1jOTB3Vgv7qDiF17wmvjhe'
        'daHiIWJAhN67cUBfvv8GfXTr0uv7fallpYSLPKjjpfLlfkk63h4crbef31q8uuk2N3uWAvNnQcOK87Jpt+IQy1DCnhXzE4B6YavrWTGJ'
        'SKy6WRMuCSJp6GgC9f6LO1gJl1h9ce+2a7Uwe+/6kZ/DKn3qrTjTx0pq5K3b+4ueFVBiJVxYSWKFkiRQ41ayaa3WHQagUJI4T3kCrMix'
        'NMKqX1CBevNo7ZevHkhvXxgIl2dFHhQJVCoS2OtXdvpVt0ENLs6CseKUmKKj89/pn+evUY3Ldro7xtsrmpdW6p7V/eMNrOiFQbFuqGk1'
        'JpUeVtaVohIGSqwecA1qJUa64u6gQWDeHVSheHjqp0fyI6Ak04SAGrcCSqyAEiuPS5QkrIRLrFyuh1Y0e/YMXGSqUz8pq2ozCh0FCjSB'
        'opqt/fL2JeISkkB5VpIH5VlRr5yWipaKlXDljThcDKklY0/CjRUhH6M0z5at+Aub7TtXtoCi872iWDmxIDEUp3ONQ41Kdf1BXK9nTJHB'
        'dooEFkisyE5x5SiMFUrRIEORT8g9O2potpqOv3FhSY8HGeyiQcm01ZBYASVWHpcoCZTkWfnnzjbzBlUyCjHuGA/OzZ999omZsdbKqkUt'
        '9PxmW9ptpZnMgJXtCvjGrSSBmrBCiaq2Vs8ozQwbVYgYs7WUUDuXfJKsWpkESo1sknpFtgqNOQzLFWulYkpHy2WJK4wcO1Ek6Ge033yY'
        'XDdhm8yb3JYSI6xszbWqZ58Qq5we5XBhWNYvD0u39hY/fPG8ByVWa/UMiZIkUGIlYcV1UgJKrFYaOcbGqlYs7JsJzM88GVb8aI6hcJG6'
        'ZMbZt3x8c5d++vyGlE9FJJmYQbAw34UrIMRlI5J5BS8My9TOpgZVR6DKGY1ZNnLp4YmBMhPzR8NK01FvbLdPmO9lJohLJ3TQzdP15TJt'
        'MZdltAlhdWVYpoNugWTGDuc0JJMKUKJuQefCOmP7TwZX3lKtZPzGVvPGdicZDRJWrx+u0Ho7KzN5kiG/tFK26GInR00m8tlqLhkRqHEr'
        'jhPGrbjWxugx15Gn3Qoopltg9eJGbb1TwOrG7oDEiskEtD+o7nTyElZLFWZzpTNamLig53ExkVusNjpFAooOlqph9ybfObjC08zV4vo1'
        '86gd4+a5zkHXFoTD5fLv375C71zd8Kyk2xe5oyIpv221liGshAso4sIuG5VndWW9vdbIiRW7/SfD6le3dk62uwhc3+kTXJcGxbatST89'
        '2UVJwoqaWZ0DJ2I6o3RxULl+vo/VO8fb/WqWNjrlRHB+leONWlqspvdt6EF9k1XNVIE618hiJYkVUHSukyeBspUwwaUE5z0oNqoJq+nd'
        'tPj4q2V1mSEpVrwNb57v0Z2Ly2JF41YkUK5Vt0zdUprGrYQLqHErrkow3SLizuXwPQFWdy4u9cumZ7VWz9JB2w2iL989kVZbxTGroli9'
        'f7xOt7a7UeZpBOZlo5qwoum1KmW0rKkClbeSN7caE1bCZSvRnZb98auH5FlJQImVQO0sVtpZ97YRrHaW6sT8W+btbDSdxVI6EvR5m9Yz'
        'U7lKjC5QL2+3sLp3vPG1VuNcJzuDfiUj7S836BJz/xYrElZ8FIoVUEaMSU1+JphhlU1GhWsarXgDslEBNWm1URMoem1vaaebFy6UJC6V'
        'elbHm22svNiosEJJOm1F7jyx0JS9DStplenKE1YkVihR09Y3qjZcdHx+mcRKAsqzev3aQc5IUMlKXF5rfYsVE014l07Z0HGGmyZ04kgb'
        'KLG6tde/vFITKM9KuMSK3rp28OmbL9D9k21CSQJqUM+LFTH3TAv5rNFsWKCIuRNFM06RaTtsYKMSqEwyfnOzca7hAHXAVdGV2qXlimc1'
        'wfXujUOshAsoBhPeuHJ+3EqU6HCRsUOfXCyr2Eni8oRwTZ0VL/7brQTKs6JxKwJKrCSgyIPyzZwVqwudHH9WTo//zWradu+8fhkW4Gzu'
        '263eu3np2vmhhJVwne/XV1pFj+twrTsoWWIF1NdaMXUNK3cWU2BhinZZ3KO82bRzhkaM1wFFQHlWBJH0/AaL7QTI4/qb1Yjrb1YlK6NE'
        'ybMCyrMKzs/IEWk85GNxo6nZWdlJsZL7I8at6PxSncatxrlOWwHlWeXUqHClWEMsuCBWQJHFZHIlLFbh6bleL1YkVi/ttN++vPbupZ7b'
        'hR5Qu4tVOm0lASWNWwmXWEUXZoFarVhSnSs7tjalVnxxX9L3snr98jkv7lmWKxRAXVltbHKfWssVA+q01fPLFbFyktxJFAZq7uxPpmvf'
        'jhXXDsL+GYF6YHXh661evbhO41bCNW5Fp62AEiugaOa5f+ROhKmzAurvWpEHNc7lWQElVsloOBcPd4wYRZhqNbISqNNW9MyUrYTJNUE/'
        'xwwC5Vpd+IoV61zRoJB69ejcBJdY0clmh4CasCIPigSKWPwQqKlbmQcrVgPDSi5vcevfrYvrkijRyXrzgdVYV1dbkkDtLVY8K+ESq4N+'
        '2Yv78KlbymDFyn5PjNUgb4xbneYSqF7BHLcSKM/KjgY8qP3FJ8oKqNNWAiVW41wCJVZ77sIRX7ESKM8KKLECanqtgDptBZRYeVCelcfl'
        'WQkUeVAkUGIlUCRQnhVNqZVAkUB9i5VweVCZREQqm6rEoVqCwc+gDysP6gmwKpmqm62vNvPSzfNd6Rc3d7zEaimvS2YiYqtuHhR3H5+2'
        'yidjl9e7EvcIs5KMxD1x3I5Kj8lNlM98p/tKtAkrBjy/1opqadWDmrCSO7U9qNNWcj+1QBW4DX46rZipgFU1qwuUZ/XhywfkKUlfayVQ'
        'YjUBddoKKM+KqWtPgJVAiZUHJVYCJY1DTVgJlFgJ1JNh1XCSWHkXaMatxqFoHMr8KhQJFHlQ5EGRQBHLjnFFbOqsSixK47AEXHxQtqTF'
        '0oO2W85Wwx4vn1LGG1Qcr2HVubbdl2R9G5K1laRO0WJCiOTelRNw52JNkVU8EsSKda08q/1B5ZustmuZcSgWO+KijGflQbXylkCd7+TH'
        'oTwr1nzASiZiTdG4KPfBxSMhzwoozwqocSugxq1kYSia2KiAEiugvtZK1scQK5ariIenxop7UFmdCSgSKLESKM9KoDwrD0qsgBKrCSjP'
        'SqAmrCg02rSmxQooseJn/CYrD0qsxqHkbfjtVh4UeeuuCJdMXZ4WKxbR4m41fkAtwV1LUXdVrlF1lm2KBLy4+8+9AXBhRo366Zu+m1yd'
        'YWUYuQYhF7ZIc9cEc1euS8bc5ChUibCGZNwcLTj2+H/JskUelGc1ASVWQFEkuMC9YN/0DVmNnCMnrITLsyIPyrPyuKZluzptBdRpK5R4'
        'ywBFf2dEOuqugMciyXB5UFZKZcW2tLtQ+RRbsYanB0UC5Vkl+ZFHce+tWP3db5hRI2LFYmsQSTkriZVwkWdF2vQ8/4vXz3rIXqWMTmkt'
        'RuNQEgvrfQcrd9cElDRh5XFp8YgUnp4pDe6Lf8g1DkWlTIrEilv/KPnd9sPZ1IP9nliNQ01YAaVMyXbFjmrCyoPyuDhYlbDSv5sVtzMD'
        '5W05E1bCNW41FeulPHjlD7kmoCSUUvGQxPDAd/q2rM2oRCRAJqAkgRKrqdi0xq1Y559n4MgapOOp0YDX95msm/JyPxRGt/R6dfM6S1NO'
        'kVWvmPasgBIryYNiFUkSqLKlfPdvjo8HNW6FkjSy8nlWj/lj+LAiVt6uZNMUDvg7BXOiKrdvPeQK+r7HB9Zo2V4XKmvp5JjJifhP6aRC'
        'PCxtKp5XKKuUCxQ9mB4c9I1bkalENXdR2e9nxRKO/PO0lcL8tJBPtjePawoGr7iBaKQ0YeWJCRRDTFhlv89CTHxiYsUTYYTLI/Ly1uFx'
        'xbToVFjFwkEvHp3QLme9zHhQoNirsCLT97LiiFSNhfkYFS72SDyacLxEJOQ1FVbuyEAk4D215CtKIyiOQrlBXqy+73cWK5XHOXDZdMQ1'
        'Lsa9+VJiSubWcosHyamfWEHEWIEkUD/YSg7PsBIu3pWSiIkSyeoNjzmUY6pSu+wQzztxe/j3jpVAkWD+gLvyszyCZGRFKA1qWYlVwyhn'
        'qMTzVekxt+LhpoTSasNRWSJMrMa4yu6NctzWpPxHrFrFDPW5O+CrUMSS0DzlKufuux73tyGDBry3WJ8WKJLPvppteGKyVgDxs/yA3W8i'
        '4ocLJUmUmL9EKHnJANfjv7/iusDoqUw5ahTSxGPyCDEWdZd5pK0cq/3zafW9f5y4uyf0J3ga2mjhFMbVUZLlxbrFNDG+SrHpmSpTy6hs'
        'X9zuF+ZJgoF54WLpcjceTDXvDrBbakj9/m8Tbo9gqaL46CZB1oqfnTlDAuU+X4MHH6Q1Tgc4qJgWq3qapSfivvmzLHcmMfg5N3MmHmK4'
        'mOc+sCr+LD/1D/vmo0P3BS5MsFYYj7JiFTL3OS6j5yZQkPspYoGIb2rWS+ExeVjFIz5TFo5WQuHAXINHAATmRhcjHsEPkogGM2oonwzG'
        '3b2Tj81Vi3F8O+9b4MB+rp5Wp8WKS07dHA/nmUmrwX4hljfjPCnhoG8rofnREN+jseLgf2fY3l+0+RshPTpfNhhrnzHjgSmyWi6yBpHa'
        'yalyoYp7+4inDW62rGhgjono//E/Ise6YWa8YsWsRCCXdBfMRCmZCCXDc0Y8kJmqNSF5wqCTDNVyOvGEU55FxWN9Wg6fUD77UVgx2ZgD'
        'URayi/rO7LQtjtXlUlHRCCrTttBov6g3HJ5ifXZY5VFW3EW40EjznCM+uZ57VH8EI8ZYJSMz2yOr/X4+FJjXowsx/5TdY7LGAxYrWqeU'
        'XmkWho1sr2R0cu6ajdwxaj+iNwgrSfJUvtWSyjJrw0a+V844erzpaDzNZLqszrWzLHLF4iXMKao5qYqtNR0lHnqUd9dixWI+aw3jcCnX'
        'LBgs2pMzE3ymMK9v6qxsLcTf9XavPKw5/aqzXDZYZf0RLrvE7V3lTPJ4rcJqkBXHYOuqOtxAHZs6Kz22wMnaa3v9wujpEnSuxbMjI9qj'
        '2/EuVawDHhmrhdbbRWoVLR6+Sc2sOkVQg2Lype3uGxdX6J0r5+5cXN1s5fd7bkbCnafxKNbhTLC8QMmI7PRKF1daNy+do5PNNvHc3kp6'
        'OuZ+LNdzQP30aOXaZntnsdQtZ6iZTfFsR0cLc6rIUPAjsUpFfdyPf7LR3O4WN9tu3Xxqd6XDEj16ImypUzCGvMtDNKrW2xd6QA1rNks9'
        'l9NKK6uNVsVZcLRI/hE9RONSP7/Eo4RbztW1+kolw/NVO+5VwtQazyuN+p1kbCqsZChmuZE/169URw+bZv12rFjay0nFH5UVNweIVSmb'
        'bldy1CpleYJ5zVYZQJ4KK3wuLJV4J/ILWqplsSL2VJzBcaqb1h7B5HOed1nJmiXHbGaNS2tNoJaaRaxIrJgostUpPOZWQBVNVXL05HgM'
        'wWFlqbFHZQUUD/4eL5NUvR7/7Spn6l9bI2tKj8SqmmG9bkvKGqmv7ZH/bP8f2sr9KQ=='
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
            assert 0 <= index < vertices and 0 <= bone < INNKEEPER_BONES, name
            assert math.isfinite(weight) and 0.0 < weight <= 1.0, name
            totals[index] += weight
        elif tag == 'skeletonlink':
            skeleton = element.get('name')
        if tag in counts:
            counts[tag] += 1
        element.clear()
    assert counts == dict(position=vertices, normal=vertices, tangent=TANGENTS[name],
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


# Triangle budget (owner decision of 2026-11-17, adapted to the approved CS10a export): total in range, fixed counts per
# material, delivered file unchanged.
def check_innkeeper_budget(mesh):
    counts = {material: len(triangles) for material, triangles in mesh['faces'].items()}
    assert counts == INNKEEPER_TRIANGLES, ('innkeeper triangles per material', counts)
    total = sum(counts.values())
    assert INNKEEPER_BUDGET[0] <= total <= INNKEEPER_BUDGET[1], ('innkeeper outside the triangle budget', total)
    with (room_file('models/Innkeeper.mesh')).open('rb') as stream:
        digest = hashlib.sha256(stream.read()).hexdigest()
    assert digest == INNKEEPER_SHA256, 'models/Innkeeper.mesh differs from the reviewed export'


# Colour of every triangle: its material's colour atlas at the triangle's UV centre (Ogre v runs downwards). Tavern
# materials come from TavernObjects.material with their ...Color.png atlas, the innkeeper figure (since CS10a) from
# FIGURE_MATERIALS with its decal texture.
def triangle_colours(mesh):
    colours, triangles = [], []
    for material in sorted(mesh['faces']):
        script_path, folder = FIGURE_MATERIALS.get(material, ('materials/scripts/TavernObjects.material',
                                                              'materials/textures/tavern/'))
        script = room_file(script_path).read_text(encoding='utf-8')
        block = re.search(r'^material ' + material + r'\s*\n\{.*?^}', script, re.M | re.S).group()
        texture = re.search(r'texture\s+(\S+Color\.png)', block) or re.search(r'texture\s+(\S+\.png)', block)
        image = np.asarray(Image.open(room_file(folder + texture.group(1))).convert('RGB'), dtype=np.float64)
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


# Render comparison (owner decision on the triangle budget; since CS10a the reference is the approved Meshy figure): the
# innkeeper seen from the game camera and from the front differs from the stored render by at most RENDER_MAX_MEAN_DIFFERENCE (mean absolute
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
        assert difference <= RENDER_MAX_MEAN_DIFFERENCE, ('the innkeeper looks different from the approved figure', view, difference)
        a, b = image.any(-1), reference.any(-1)
        overlap = (a & b).sum() / max((a | b).sum(), 1)
        assert overlap >= RENDER_MIN_SILHOUETTE_OVERLAP, ('the innkeeper has another silhouette than the approved figure', view, overlap)
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
        look = check_innkeeper_render(meshes['Innkeeper'])
        skeleton = ET.parse(deserialize('Innkeeper.skeleton', directory)).getroot()
        assert len(skeleton.findall('./bones/bone')) == INNKEEPER_BONES
        clips = {a.get('name'): float(a.get('length'))
                 for a in skeleton.findall('./animations/animation')}
        assert clips == CLIPS, clips
        for animation in skeleton.findall('./animations/animation'):
            assert animation.findall('./tracks/track/keyframes/keyframe'), animation.get('name')
        print('ODP_TEST_PHASE ' + json.dumps({'name': 'validation', 'seconds': time.perf_counter() - prepared}))
    print('check_tavern_approved_models: ok (2 native meshes, %d bones, 3 clips, 12 atlases; innkeeper %d triangles, '
          'render difference/overlap %s)' % (INNKEEPER_BONES, sum(INNKEEPER_TRIANGLES.values()), look))


if __name__ == '__main__':
    main()
