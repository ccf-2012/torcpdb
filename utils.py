

GENRE_IDS = {28: '动作', 12: '冒险', 16: '动画', 35: '喜剧', 80: '犯罪', 99: '纪录', 18: '剧情', 10751: '家庭',
             14: '奇幻', 36: '历史', 27: '恐怖', 10402: '音乐', 9648: '悬疑', 10749: '爱情', 878: '科幻', 10770: '电视电影',
             53: '惊悚', 10752: '战争', 37: '西部', 10759: '动作冒险', 10762: '儿童', 10763: '新闻', 10764: '真人秀', 
             10765: '科幻奇幻', 10766: '肥皂剧', 10767: '脱口秀', 10768: '战争政治'}


def tryint(instr):
    try:
        string_int = int(instr)
    except ValueError:    
        string_int = 0
    return string_int


def genreid2str(idstr):
    if not idstr:
        return ''
    idlist = [tryint(z) for z in idstr.split(',')]
    genre_names = ''
    if idlist:
        genre_names = [GENRE_IDS.get(id, '') for id in idlist if id in GENRE_IDS]
    
    # 返回结果，空格分隔
    return ' '.join(genre_names)


def truncate_string(input_string, max_length=128):
    if not input_string:
        return ''
    input_string = input_string.strip()
    # 如果字符串的长度大于最大长度，则截取并加上 '...'
    if len(input_string) > max_length:
        return input_string[:max_length] + '...'
    else:
        return input_string
