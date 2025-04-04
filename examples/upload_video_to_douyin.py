import asyncio
import argparse
from pathlib import Path

from conf import BASE_DIR
from uploader.douyin_uploader.main import douyin_setup, DouYinVideo
from utils.files_times import generate_schedule_time_next_day, get_title_and_hashtags


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="上传视频到抖音")
    parser.add_argument("account_name", type=str, help="账户名称，如Epodak", nargs="?", default="Epodak")
    args = parser.parse_args()
    
    filepath = Path(BASE_DIR) / "videos"
    # 使用与CLI一致的路径格式
    account_file = Path(BASE_DIR / "cookies" / f"douyin_{args.account_name}.json")
    
    print(f"使用账户: {args.account_name}")
    print(f"Cookie文件: {account_file}")
    
    # 获取视频目录
    folder_path = Path(filepath)
    # 获取文件夹中的所有文件
    files = list(folder_path.glob("*.mp4"))
    file_num = len(files)
    
    if not files:
        print(f"错误: 在 {filepath} 目录下未找到任何视频文件")
        exit(1)
        
    print(f"找到 {file_num} 个视频文件，准备上传")
    publish_datetimes = generate_schedule_time_next_day(file_num, 1, daily_times=[16])
    cookie_setup = asyncio.run(douyin_setup(str(account_file), handle=True))
    
    if not cookie_setup:
        print("Cookie验证失败，请先登录")
        exit(1)
        
    for index, file in enumerate(files):
        title, tags = get_title_and_hashtags(str(file))
        thumbnail_path = file.with_suffix('.png')
        # 打印视频文件名、标题和 hashtag
        print(f"正在处理第 {index+1}/{file_num} 个视频")
        print(f"视频文件名：{file}")
        print(f"标题：{title}")
        print(f"Hashtag：{tags}")
        
        if thumbnail_path.exists():
            print(f"使用自定义封面: {thumbnail_path}")
            app = DouYinVideo(title, file, tags, publish_datetimes[index], account_file, thumbnail_path=thumbnail_path)
        else:
            print("使用系统生成的封面")
            app = DouYinVideo(title, file, tags, publish_datetimes[index], account_file)
            
        try:
            asyncio.run(app.main(), debug=False)
            print(f"第 {index+1}/{file_num} 个视频处理完成")
        except Exception as e:
            print(f"处理视频时出错: {str(e)}")
            if index < file_num - 1:
                print("错误后继续处理下一个视频...")
