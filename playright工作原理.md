---
marp: true
theme: am_blue
paginate: true
math: katex
headingDivider: [2,3,4,5]
backgroundColor: #D0E8D6DA
---
## Playwright基本概念

Playwright是一个自动化浏览器测试工具，在你的项目中用于:

1. **浏览器自动化** - 控制Chrome/Firefox/Safari等浏览器
2. **页面交互** - 点击、输入、选择元素等
3. **文件上传** - 自动上传视频和图片
4. **等待和导航** - 等待页面加载和导航
5. **状态管理** - 保存和使用cookie维持登录状态

## 主要组件和步骤

### 1. 初始化Playwright实例

```python
async with async_playwright() as playwright:
    # 在这里使用playwright
```

### 2. 启动浏览器

```python
browser = await playwright.chromium.launch(
    headless=False,  # 是否显示浏览器界面
    executable_path=LOCAL_CHROME_PATH,  # 本地Chrome路径
    args=['--disable-blink-features=AutomationControlled']  # 浏览器启动参数
)
```

### 3. 创建浏览器上下文

```python
context = await browser.new_context(
    storage_state=account_file,  # cookie文件路径
    viewport={"width": 1280, "height": 800}  # 视口大小
)
```

### 4. 创建页面并导航

```python
page = await context.new_page()
await page.goto("https://creator.douyin.com/creator-micro/content/upload")
```

### 5. 页面交互

```python
# 点击元素
await page.click('selector')

# 输入文本
await page.fill('selector', 'text')

# 上传文件
await page.locator('input[type="file"]').set_input_files(file_path)

# 等待元素出现
await page.wait_for_selector('selector', timeout=10000)

# 等待导航完成
await page.wait_for_url("https://example.com", timeout=10000)

# 截图
await page.screenshot(path="screenshot.png")
```

## 可参数化的部分

你可以对以下方面进行参数化:

1. **浏览器配置**:
   - `headless`: 是否显示浏览器界面
   - `slow_mo`: 操作间延迟时间(毫秒)
   - `timeout`: 全局超时设置

2. **页面导航**:
   - `timeout`: 导航超时时间
   - `wait_until`: 等待页面加载的条件

3. **元素选择器**:
   - CSS选择器
   - XPath
   - 文本内容

4. **等待时间**:
   - 各种操作的超时设置
   - 自定义等待间隔

5. **文件路径**:
   - 上传文件的路径
   - 截图保存路径

## 添加新的Playwright自动化功能

假设你想添加新的平台（如"小红书"）支持，步骤如下:

1. **创建新的上传类**:

```python
# uploader/xiaohongshu_uploader/main.py
class XiaoHongShuVideo(object):
    def __init__(self, title, file_path, tags, publish_date, account_file, thumbnail_path=None):
        self.title = title
        self.file_path = file_path
        self.tags = tags
        self.publish_date = publish_date
        self.account_file = account_file
        self.thumbnail_path = thumbnail_path
        
    async def upload(self, playwright: Playwright) -> None:
        # 1. 启动浏览器
        browser = await playwright.chromium.launch(headless=False)
        
        # 2. 创建上下文
        context = await browser.new_context(storage_state=self.account_file)
        
        # 3. 打开页面
        page = await context.new_page()
        await page.goto("https://creator.xiaohongshu.com/publish")
        
        # 4. 上传视频
        try:
            # 直接设置文件输入(最可靠的方法)
            await page.locator('input[type="file"]').set_input_files(self.file_path)
            
            # 5. 填写标题
            await page.fill('input[placeholder="添加标题"]', self.title)
            
            # 6. 添加标签
            for tag in self.tags:
                await page.fill('input[placeholder="添加标签"]', tag)
                await page.press('input[placeholder="添加标签"]', 'Enter')
                
            # 7. 发布
            await page.click('button:has-text("发布")')
            
            # 8. 等待发布完成
            await page.wait_for_url("https://creator.xiaohongshu.com/content/manage")
            
        finally:
            # 保存cookie
            await context.storage_state(path=self.account_file)
            await context.close()
            await browser.close()
```

2. **添加获取cookie功能**:

```python
async def get_xiaohongshu_cookie(account_file):
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()
        
        await page.goto("https://creator.xiaohongshu.com/login")
        # 等待用户登录
        await page.wait_for_url("https://creator.xiaohongshu.com/home", timeout=300000)
        
        # 保存cookie
        await context.storage_state(path=account_file)
        await context.close()
        await browser.close()
```

3. **创建cli接口**:

```python
# examples/upload_video_to_xiaohongshu.py
import argparse
import os
import asyncio
from uploader.xiaohongshu_uploader.main import XiaoHongShuVideo
from datetime import datetime

async def main():
    parser = argparse.ArgumentParser(description='上传视频到小红书')
    parser.add_argument('account_name', help='账号名称')
    parser.add_argument('video_path', help='视频文件路径')
    parser.add_argument('-t', '--tags', nargs='+', default=[], help='标签列表')
    parser.add_argument('-pt', '--publish_time', type=int, default=0, help='发布时间(0为立即发布)')
    args = parser.parse_args()
    
    # 构建cookie路径
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    cookie_path = os.path.join(BASE_DIR, 'cookies', f'xiaohongshu_{args.account_name}.json')
    
    # 获取视频标题和标签
    video_name = os.path.splitext(os.path.basename(args.video_path))[0]
    
    # 创建XiaoHongShuVideo实例
    video = XiaoHongShuVideo(
        title=video_name,
        file_path=args.video_path,
        tags=args.tags,
        publish_date=datetime.now() if args.publish_time == 0 else datetime.fromtimestamp(args.publish_time),
        account_file=cookie_path
    )
    
    # 执行上传
    await video.main()

if __name__ == "__main__":
    asyncio.run(main())
```

## Playwright常用选择器技巧

1. **多种定位元素的方式**:
   ```python
   # CSS选择器
   page.locator('div.upload-btn')
   
   # 包含文本的元素
   page.locator('div:has-text("上传视频")')
   
   # 角色选择器
   page.get_by_role('button', name='发布')
   
   # 文本选择器
   page.get_by_text('上传视频')
   ```

2. **等待元素状态**:
   ```python
   await page.wait_for_selector('selector', state='visible')
   await page.wait_for_load_state('networkidle')
   ```

3. **处理文件上传(3种方法)**:
   ```python
   # 方法1: 直接设置文件输入
   await page.locator('input[type="file"]').set_input_files(file_path)
   
   # 方法2: 点击并使用文件选择器
   async with page.expect_file_chooser() as fc_info:
       await page.click('button.upload')
   file_chooser = await fc_info.value
   await file_chooser.set_files(file_path)
   
   # 方法3: 使用JavaScript
   await page.evaluate("""
   () => {
       const input = document.querySelector('input[type="file"]');
       input.style.opacity = '1';
       input.style.visibility = 'visible';
   }
   """)
   await page.locator('input[type="file"]').set_input_files(file_path)
   ```

## 调试和错误处理技巧

1. **截图调试**:
   ```python
   await page.screenshot(path="debug.png")
   ```

2. **超时处理**:
   ```python
   try:
       await page.wait_for_selector('selector', timeout=10000)
   except Exception as e:
       print(f"超时错误: {e}")
       # 处理超时情况
   ```

3. **查询元素状态**:
   ```python
   is_visible = await page.locator('selector').is_visible()
   element_count = await page.locator('selector').count()
   ```

这些Playwright自动化技术可以应用于任何Web平台，不仅仅是抖音。通过理解这些核心概念，你可以轻松扩展你的自动上传工具以支持更多平台。
