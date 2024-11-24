# TORCP2DB

* 以 api 接口形式，提供对 TMDb/IMDb 的查询
* 本地缓存查询结果
* 以 web ui 形式提供本地缓存数据库的查询、修改
* 与 torcp2 对应，这是 server 端

## api 接口
1. /api/query
```
    查询种子名称对应的媒体信息
    
    Args:
        seed_name (str): 需要查询的种子名称
        api_url (str): API基础URL地址
    
    Returns:
        dict: 查询结果
            成功返回示例:
            {
                'success': True,
                'data': {
                    'id': 1,
                    'seed_name': '示例种子名',
                    'media_name': '正确的媒体名称',
                    'category': '电影',
                    'tmdb_id': 12345,
                    'year': 2024,
                    'created_at': '2024-01-01 12:00:00'
                }
            }
            
            失败返回示例:
            {
                'success': False,
                'message': '未找到匹配记录'
            }
    
    Raises:
        requests.RequestException: 当API请求失败时抛出异常
```
2. /api/record
```
    记录媒体信息到数据库
    
    Args:
        media_info (dict): 媒体信息字典，必须包含以下字段:
            - seed_name: 种子名称
            - media_name: 媒体名称
            - category: 分类
            - tmdb_id: TMDB ID
            - year: 年份
        api_url (str): API基础URL地址
    
    Returns:
        dict: API响应结果
            成功返回示例:
            {
                'success': True,
                'data': {
                    'id': 1,
                    'seed_name': '示例种子名',
                    'media_name': '正确的媒体名称',
                    'category': '电影',
                    'tmdb_id': 12345,
                    'year': 2024,
                    'created_at': '2024-01-01 12:00:00'
                }
            }
    
    Raises:
        requests.RequestException: 当API请求失败时抛出异常
        ValueError: 当提供的media_info缺少必要字段时抛出异常
```

