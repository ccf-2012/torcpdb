
from tmdbv3api import TMDb, Movie, TV, Search, Find
from imdb import Cinemagoer
import re
import time
from loguru import logger

def tryint(instr):
    try:
        string_int = int(instr)
    except ValueError:    
        string_int = 0
    return string_int

class TMDbSearcher():
    def __init__(self, tmdb_api_key, tmdb_lang):
        if tmdb_api_key:
            self.tmdb = TMDb()
            self.tmdb.api_key = tmdb_api_key
            self.tmdb.language = tmdb_lang
        else:
            self.tmdb = None


    def searchTMDbByTMDbId(self, torinfo, tmdbid):
        r = False
        if torinfo.tmdb_cat == 'tv':
            r = self.searchTMDbByTMDbIdTv(torinfo, tmdbid)
        elif torinfo.tmdb_cat == 'movie':
            r = self.searchTMDbByTMDbIdMovie(torinfo, tmdbid)
        else:
            r = self.searchTMDbByTMDbIdTv(torinfo, tmdbid)
            if not r:
                r = self.searchTMDbByTMDbIdMovie(torinfo, tmdbid)
        if r:
            r = self.fillDetails(torinfo)
        return r

    def searchTMDbByTMDbIdTv(self, torinfo, tmdbid):
        tv = TV(self.tmdb)
        logger.info("Search tmdbid in TV: " + tmdbid)
        try:
            t = tv.details(tmdbid)
            if t:
                torinfo.tmdbDetails = t
                self.saveTmdbTVResultMatch(torinfo, t)
                return True
        except:
            pass
        return False

    def searchTMDbByTMDbIdMovie(self, torinfo, tmdbid):
        movie = Movie(self.tmdb)
        logger.info("Search tmdbid in Movie: " + tmdbid)
        try:
            m = movie.details(tmdbid)
            if m:
                torinfo.tmdbDetails = m
                self.saveTmdbMovieResult(torinfo, m)
                return True
        except:
            pass
        return False
    
    def saveTmdbTVResultMatch(self, torinfo, result):
        if result:
            if hasattr(result, 'name'):
                torinfo.media_title = result.name
                # print('name: ' + result.name)
            elif hasattr(result, 'original_name'):
                torinfo.media_title = result.original_name
                # print('original_name: ' + result.original_name)
            torinfo.tmdb_id = result.id
            torinfo.tmdb_cat = 'tv'
            if hasattr(result, 'original_language'):
                if result.original_language == 'zh':
                    torinfo.original_language = 'cn'
                else:
                    torinfo.original_language = result.original_language
            if hasattr(result, 'popularity'):
                torinfo.popularity = result.popularity
            if hasattr(result, 'poster_path'):
                torinfo.poster_path = result.poster_path
            if hasattr(result, 'first_air_date'):
                torinfo.year = self.getYear(result.first_air_date)
                torinfo.release_air_date = result.first_air_date
            elif hasattr(result, 'release_date'):
                torinfo.year = self.getYear(result.release_date)
                torinfo.release_air_date = result.release_date
            else:
                torinfo.year = 0
            if hasattr(result, 'genres'):
                torinfo.genre_ids = [x['id'] for x in result.genres]
            if hasattr(result, 'genre_ids'):
                torinfo.genre_ids = result.genre_ids
            logger.info('Found [%d]: %s' % (torinfo.tmdb_id, torinfo.media_title))
        else:
            logger.info('Not match in tmdb: [%s] ' % (torinfo.media_title))

        return result is not None


    def saveTmdbMovieResult(self, torinfo, result):
        if hasattr(result, 'title'):
            torinfo.media_title = result.title
        elif hasattr(result, 'original_title'):
            torinfo.media_title = result.original_title
        # if hasattr(result, 'media_type'):
        #     self.ccfcat = transToCCFCat(result.media_type, self.ccfcat)
        torinfo.tmdb_id = result.id
        torinfo.tmdb_cat = 'movie'
        if hasattr(result, 'original_language'):
            if result.original_language == 'zh':
                torinfo.original_language = 'cn'
            else:
                torinfo.original_language = result.original_language
        if hasattr(result, 'popularity'):
            torinfo.popularity = result.popularity
        if hasattr(result, 'poster_path'):
            torinfo.poster_path = result.poster_path
        if hasattr(result, 'release_date'):
            torinfo.year = self.getYear(result.release_date)
            torinfo.release_air_date = result.release_date
        elif hasattr(result, 'first_air_date'):
            torinfo.year = self.getYear(result.first_air_date)
            torinfo.release_air_date = result.first_air_date
        else:
            torinfo.year = 0
        if hasattr(result, 'genres'):
            torinfo.genre_ids = [x['id'] for x in result.genres]
        if hasattr(result, 'genre_ids'):
            torinfo.genre_ids = result.genre_ids
        
        logger.info('Found [%d]: %s' % (torinfo.tmdb_id, torinfo.media_title))
        return True

    def getYear(self, datestr):
        intyear = 0
        m2 = re.search(
            r'\b((19\d{2}\b|20\d{2})(-19\d{2}|-20\d{2})?)',
            datestr,
            flags=re.A | re.I)
        if m2:
            yearstr = m2.group(2)
            intyear = tryint(yearstr)
        return intyear


    def getTitle(self, result):
        tt = ''
        if hasattr(result, 'name'):
            tt = result.name
        elif hasattr(result, 'title'):
            tt = result.title
        elif hasattr(result, 'original_name'):
            tt = result.original_name
        elif hasattr(result, 'original_title'):
            tt = result.original_title
        return tt

    def containsCJK(self, str):
        return re.search(r'[\u4e00-\u9fa5]', str)

    def searchTMDbByIMDbId(self, torinfo, imdbid):
        torinfo.imdb_id = self.getIMDbInfo(torinfo, imdbid)
        r = self._searchTMDbByIMDbId(torinfo, torinfo.imdb_id)
        if r:
            self.fillDetails(torinfo)
        return r
    
    def _searchTMDbByIMDbId(self, torinfo, imdbid):
        f = Find(imdbid)
        logger.info("Search : " + imdbid)
        t = f.find_by_imdb_id(imdb_id=imdbid)
        if t:
            # print(t)
# (Pdb) p t.movie_results
# [{'adult': False, 'backdrop_path': '/rcmjVmKBKONXk2LCe7GOAIHaIAO.jpg', 'id': 1068249, 'title': 'Reborn Rich', 'original_language': 'ko', 'original_title': '재벌집 막내아들', 'overview': '...', 'poster_path': '/xVtekQdaJ00cQqK2oyVJg5P7a6H.jpg', 'media_type': 'movie', 'genre_ids': [18, 14], 'popularity': 1.4, 'release_date': '2022-11-18', 'video': False, 'vote_average': 0.0, 'vote_count': 0}]
# (Pdb) t.tv_results
# [{'adult': False, 'backdrop_path': '/jG8mKDxe0LIDFBPB8uCeYGSBWCH.jpg', 'id': 153496, 'name': 'Reborn Rich', 'original_language': 'ko', 'original_name': '재벌집 막내아들', 'overview': '....', 'poster_path': '/ioywelRYOfNJ5w8aNQ5ttJo9dk1.jpg', 'media_type': 'tv', 'genre_ids': [18, 10765], 'popularity': 70.232, 'first_air_date': '2022-11-18', 'vote_average': 8.094, 'vote_count': 32, 'origin_country': ['KR']}]
            if torinfo.tmdb_cat == "tv":
                if t.tv_results:
                    torinfo.tmdb_cat = "tv"
                    r = t['tv_results'][0]
                    self.saveTmdbTVResultMatch(torinfo, r)
                    return True
                elif t.movie_results:
                    torinfo.tmdb_cat = "movie"
                    r = t['movie_results'][0]
                    self.saveTmdbMovieResult(torinfo, r)
                    return True
                else:
                    pass
            else: 
                if t.movie_results:
                    torinfo.tmdb_cat = "movie"
                    r = t['movie_results'][0]
                    self.saveTmdbMovieResult(torinfo, r)
                    return True
                elif t.tv_results:
                    torinfo.tmdb_cat = "tv"
                    r = t['tv_results'][0]
                    self.saveTmdbTVResultMatch(torinfo, r)
                    return True
                else:
                    pass
        return False

    def replaceRomanNum(self, titlestr):
        # no I and X
        romanNum = [ (r'\bII\b', '2'), (r'\bIII\b', '3'), (r'\bIV\b', '4'), (r'\bV\b', '5'), (r'\bVI\b', '6'), (r'\bVII\b', '7'), (r'\bVIII\b', '8'),
                    (r'\bIX\b', '9'), (r'\bXI\b', '11'), (r'\bXII\b', '12'), (r'\bXIII\b', '13'), (r'\bXIV\b', '14'), (r'\bXV\b', '15'), (r'\bXVI\b', '16')]
        for s in romanNum:
            titlestr = re.sub(s[0], s[1], titlestr, flags=re.A)
        return titlestr

    def fixTmdbParam(self, tparam):
        if "year" in tparam and len(tparam["year"]) != 4:
            del tparam["year"]
        return tparam

    def selectOrder(self, cntitle, cuttitle, list):
        if len(cntitle) < 3 and len(cuttitle)> 5:
            list[0], list[1] = list[1], list[0]
            return list
        else:
            return list

    def findYearMatch(self, results, year, strict=True):
        matchList = []
        for result in results:
            if year == 0:
                matchList.append(result)
                continue

            datestr = ''
            if hasattr(result, 'first_air_date'):
                datestr = result.first_air_date
            elif hasattr(result, 'release_date'):
                datestr = result.release_date

            resyear = self.getYear(datestr)
                # return result

            if strict:
                if resyear == year:
                    matchList.append(result)
                    continue
            else:
                if resyear in [year-3, year-2, year-1, year, year+1]:
                    self.year = resyear
                    matchList.append(result)
                    continue

        if len(matchList) > 0:
            # prefer item with CJK
            if self.tmdb.language == 'zh-CN':
                for item in matchList[:3]:
                    tt = self.getTitle(item)
                    if not tt:
                        continue
                    if self.containsCJK(tt):
                        return item
            return matchList[0]
        return None

    def saveTmdbMultiResult(self, torinfo, result):
        if hasattr(result, 'media_type'):
            torinfo.tmdb_cat = result.media_type
            if result.media_type == 'tv':
                self.saveTmdbTVResultMatch(torinfo, result)
            elif result.media_type == 'movie':
                self.saveTmdbMovieResult(torinfo, result)
            else:
                logger.info('Unknow media_type %s ' % result.media_type)
        return
    
    def searchTMDb(self, torinfo):
        r = self._searchTMDb(torinfo)
        if r:
            self.fillDetails(torinfo)
        return r

    def _searchTMDb(self, torinfo):
        searchList = []
        title = torinfo.media_title
        cntitle = torinfo.subtitle
        intyear = torinfo.year

        if title == cntitle:
            cntitle = ''
        cuttitle = re.sub(r'^(Jade|\w{2,3}TV)\s+', '', title, flags=re.I)
        cuttitle = re.sub(r'\b(Extended|Anthology|Trilogy|Quadrilogy|Tetralogy|Collections?)\s*$', '', title, flags=re.I)
        cuttitle = re.sub(r'\b(Extended|HD|S\d+|E\d+|V\d+|4K|DVD|CORRECTED|UnCut|SP)\s*$', '', cuttitle, flags=re.I)
        cuttitle = re.sub(r'^\s*(剧集|BBC：?|TLOTR|Jade|Documentary|【[^】]*】)', '', cuttitle, flags=re.I)
        cuttitle = re.sub(r'(\d+部曲|全\d+集.*|原盘|系列|\s[^\s]*压制.*)\s*$', '', cuttitle, flags=re.I)
        cuttitle = re.sub(r'(\b国粤双语|[\b\(]?\w+版|\b\d+集全).*$', '', cuttitle, flags=re.I)
        cuttitle = re.sub(r'(The[\s\.]*(Complete\w*|Drama\w*|Animate\w*)?[\s\.]*Series|The\s*Movie)\s*$', '', cuttitle, flags=re.I)
        cuttitle = re.sub(r'\b(Season\s?\d+)\b', '', cuttitle, flags=re.I)
        if cntitle:
            cntitle = re.sub(r'(\d+部曲|全\d+集.*|原盘|系列|\s[^\s]*压制.*)\s*$', '', cntitle, flags=re.I)
            cntitle = re.sub(r'(\b国粤双语|[\b\(]?\w+版|\b\d+集全).*$', '', cntitle, flags=re.I)

        cuttitle = self.replaceRomanNum(cuttitle)

        m1 = re.search(r'the movie\s*$', cuttitle, flags=re.A | re.I)        
        if m1 and m1.span(0)[0] > 0:
            cuttitle = cuttitle[:m1.span(0)[0]].strip()
            torinfo.tmdb_cat = 'movie'

        m2 = re.search(
            r'\b((19\d{2}\b|20\d{2})(-19\d{2}|-20\d{2})?)\b(?!.*\b\d{4}\b.*)',
            cuttitle,
            flags=re.A | re.I)
        if m2 and m2.span(1)[0] > 0:
            cuttitle = cuttitle[:m2.span(1)[0]].strip()
            cuttitle2 = cuttitle[m2.span(1)[1]:].strip()

        if torinfo.season:
            searchList = self.selectOrder(cntitle, cuttitle, [('tv', cntitle), ('tv', cuttitle), ('multi', cntitle)])
        elif torinfo.tmdb_cat.lower() == 'tv':
            searchList = self.selectOrder(cntitle, cuttitle, [('multi', cntitle), ('tv', cuttitle), ('multi', cuttitle)])
        elif torinfo.tmdb_cat.lower() == 'hdtv':
            searchList = [('multi', cntitle), ('multi', cuttitle)]
        elif torinfo.tmdb_cat.lower() == 'movie':
            searchList = self.selectOrder(cntitle, cuttitle, [('movie', cntitle), ('multi', cntitle), ('movie', cuttitle), ('multi', cuttitle)])
        else:
            searchList = [('multi', cntitle), ('multi', cuttitle)]

        for s in searchList:
            if s[0] == 'tv' and s[1]:
                logger.info('Search TV: ' + s[1])
                # tv = TV()
                # results = tv.search(s[1])
                search = Search()

                results = search.tv_shows(self.fixTmdbParam({"query": s[1], "year": str(intyear), "page": 1}))
                if len(results) > 0:
                    if intyear > 0:
                        if torinfo.season and 'S01' not in torinfo.season:
                            intyear = 0
                    result = self.findYearMatch(results, intyear, strict=True)
                    if result:
                        self.saveTmdbTVResultMatch(torinfo, result)
                        return True
                    else:
                        result = self.findYearMatch(results, intyear, strict=False)
                        if result:
                            self.saveTmdbTVResultMatch(torinfo, result)
                            return True

            elif s[0] == 'movie' and s[1]:
                logger.info('Search Movie:  %s (%d)' % (s[1], intyear))
                search = Search()
                if intyear == 0:
                    results = search.movies({"query": s[1], "page": 1})
                else:
                    results = search.movies(self.fixTmdbParam({"query": s[1], "year": str(intyear), "page": 1}))

                if len(results) > 0:
                    result = self.findYearMatch(results, intyear, strict=True)
                    if result:
                        self.saveTmdbMovieResult(torinfo, result)
                        return True
                    else:
                        result = self.findYearMatch(results, intyear, strict=False)
                        if result:
                            self.saveTmdbMovieResult(torinfo, result)
                            return True
                elif intyear > 0:
                    results = search.movies({"query": s[1], "page": 1})
                    if len(results) > 0:
                        result = self.findYearMatch(results, intyear, strict=False)
                        if result:
                            self.saveTmdbMovieResult(torinfo, result)
                            return True
            elif s[0] == 'multi' and s[1]:
                logger.info('Search Multi:  %s (%d)' % (s[1], intyear))
                search = Search()
                if intyear == 0:
                    results = search.multi({"query": s[1], "page": 1})
                else:
                    results = search.multi(self.fixTmdbParam({"query": s[1], "year": str(intyear), "page": 1}))

                if len(results) > 0:
                    result = self.findYearMatch(results, intyear, strict=True)
                    if result:
                        self.saveTmdbMultiResult(torinfo, result)
                        return True
                    else:
                        result = self.findYearMatch(results, intyear, strict=False)
                        if result:
                            self.saveTmdbMultiResult(torinfo, result)
                            return True
                elif intyear > 0:
                    results = search.multi({"query": s[1], "page": 1})
                    if len(results) > 0:
                        result = self.findYearMatch(results, intyear, strict=True)
                        if result:
                            self.saveTmdbMultiResult(torinfo, result)
                            return True
                        else:
                            result = self.findYearMatch(results, intyear, strict=False)
                            if result:
                                self.saveTmdbMultiResult(torinfo, result)
                                return True

        logger.info('TMDb Not found: [%s] [%s] ' % (title, cntitle))
        return False



    def getIMDbInfo(self, torinfo, imdb_id):
        ia = Cinemagoer()
        torinfo.imdb_id = imdb_id
        try:
            movie = ia.get_movie(imdb_id[2:])
            torinfo.imdb_val = movie.get('rating')
            # 检查是否是电视剧
            if movie.get('kind') in [ 'episode'] :
                torinfo.imdb_id = 'tt'+movie.get('episode of').movieID
                logger.error(f"提供的ID {imdb_id} 是个 episode, 剧集 为 {torinfo.imdb_id}")
        except Exception as e:
            logger.error(f"获取 IMDb 信息时发生错误: {e}")
        return torinfo.imdb_id

    def getDetails(self, torinfo):
        attempts = 0
        while attempts < 3:
            try:
                if torinfo.tmdb_id > 0:
                    if torinfo.tmdb_cat == 'movie':
                        movie = Movie()
                        torinfo.tmdbDetails = movie.details(torinfo.tmdb_id)
                    elif torinfo.tmdb_cat == 'tv':
                        tv = TV()
                        torinfo.tmdbDetails = tv.details(torinfo.tmdb_id)
                break
            except:
                attempts += 1
                logger.warning("TMDb connection failed. Trying %d " % attempts)
                time.sleep(3)

    def fillDetails(self, torinfo):
        if not torinfo.tmdbDetails:
            self.getDetails(torinfo)
        if torinfo.tmdbDetails:
            if torinfo.tmdbDetails.origin_country:
                torinfo.origin_country = torinfo.tmdbDetails.origin_country[0]
            if hasattr(torinfo.tmdbDetails, 'original_title'):
                torinfo.original_title = torinfo.tmdbDetails.original_title
            if hasattr(torinfo.tmdbDetails, 'overview'):
                torinfo.overview = torinfo.tmdbDetails.overview
            if hasattr(torinfo.tmdbDetails, 'vote_average'):
                torinfo.vote_average = torinfo.tmdbDetails.vote_average
            if torinfo.tmdbDetails.production_countries:
                if 'iso_3166_1' in torinfo.tmdbDetails.production_countries[0]:
                    torinfo.production_countries = torinfo.tmdbDetails.production_countries[0]['iso_3166_1']
            return torinfo
        return torinfo
