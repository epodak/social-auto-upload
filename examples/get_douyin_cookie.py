import asyncio
from pathlib import Path
import sys
import argparse

# 添加项目根目录到Python路径
sys.path.append(str(Path(__file__).parent.parent))
from conf import BASE_DIR
from uploader.douyin_uploader.main import douyin_setup

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="获取抖音账号的cookie")
    parser.add_argument("account_name", type=str, help="账户名称，如Epodak", nargs="?", default="Epodak")
    args = parser.parse_args()
    
    # 使用与CLI一致的路径格式
    account_file = Path(BASE_DIR / "cookies" / f"douyin_{args.account_name}.json")
    account_file.parent.mkdir(exist_ok=True)
    
    print(f"正在为账户 {args.account_name} 获取cookie...")
    print(f"Cookie将保存到: {account_file}")
    cookie_setup = asyncio.run(douyin_setup(str(account_file), handle=True))
