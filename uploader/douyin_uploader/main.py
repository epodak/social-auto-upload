# -*- coding: utf-8 -*-
from datetime import datetime

from playwright.async_api import Playwright, async_playwright, Page
import os
import asyncio

from conf import LOCAL_CHROME_PATH
from utils.base_social_media import set_init_script
from utils.log import douyin_logger


async def cookie_auth(account_file):
    async with async_playwright() as playwright:
        try:
            browser = await playwright.chromium.launch(headless=True)
            context = await browser.new_context(storage_state=account_file)
            context = await set_init_script(context)
            # 创建一个新的页面
            page = await context.new_page()
            # 访问指定的 URL
            await page.goto("https://creator.douyin.com/creator-micro/content/upload", timeout=30000)
            try:
                await page.wait_for_url("https://creator.douyin.com/creator-micro/content/upload", timeout=10000)
            except:
                douyin_logger.warning("[+] cookie 失效或加载超时")
                await context.close()
                await browser.close()
                return False

            # 检查是否有登录按钮或登录相关文本
            login_elements = ['手机号登录', '登录', '注册', '登入', '快速登录']
            for login_text in login_elements:
                if await page.get_by_text(login_text, exact=True).count():
                    douyin_logger.warning(f"[+] 检测到登录相关文本 '{login_text}'，cookie 已失效")
                    await context.close()
                    await browser.close()
                    return False
            
            douyin_logger.info("[+] cookie 验证成功")
            await context.close()
            await browser.close()
            return True
        except Exception as e:
            douyin_logger.error(f"[+] cookie 验证过程出错: {str(e)}")
            return False


async def douyin_setup(account_file, handle=False):
    try:
        # 验证cookie有效性，处理cookie不存在或失效的情况
        cookie_valid = False
        if os.path.exists(account_file):
            douyin_logger.info("[+] 验证cookie有效性...")
            cookie_valid = await cookie_auth(account_file)
            
        if not cookie_valid:
            if not handle:
                douyin_logger.error("[+] cookie无效，但未授权自动登录")
                return False
                
            douyin_logger.info('[+] cookie文件不存在或已失效，即将自动打开浏览器，请扫码登录')
            await get_douyin_cookie(account_file)
            
            # 验证新获取的cookie
            retry_count = 0
            while retry_count < 3:
                if await cookie_auth(account_file):
                    douyin_logger.success("[+] 新cookie验证成功!")
                    return True
                douyin_logger.warning(f"[+] 新cookie验证失败，等待5秒后重试 ({retry_count+1}/3)")
                await asyncio.sleep(5)
                retry_count += 1
                
            douyin_logger.error("[+] 多次尝试后cookie仍然无效，请检查登录状态")
            return False
        return True
    except Exception as e:
        douyin_logger.error(f"[+] 设置过程出错: {str(e)}")
        return False


async def get_douyin_cookie(account_file):
    async with async_playwright() as playwright:
        try:
            options = {
                'headless': False,
                'args': ['--disable-blink-features=AutomationControlled']
            }
            
            # 尝试使用本地Chrome
            if LOCAL_CHROME_PATH:
                browser = await playwright.chromium.launch(executable_path=LOCAL_CHROME_PATH, **options)
            else:
                browser = await playwright.chromium.launch(**options)
                
            context = await browser.new_context(viewport={"width": 1280, "height": 800})
            context = await set_init_script(context)
            
            page = await context.new_page()
            douyin_logger.info("[+] 正在打开抖音创作者页面，请在弹出的浏览器中登录...")
            await page.goto("https://creator.douyin.com/")
            
            # 等待用户手动登录完成
            douyin_logger.info("[+] 请在浏览器中完成登录，登录成功后系统将自动保存cookie")
            
            # 等待用户登录成功并跳转到主页
            max_wait_time = 300  # 最多等待5分钟
            successful_login = False
            
            for _ in range(max_wait_time):
                # 检查是否已登录成功
                if page.url.startswith("https://creator.douyin.com/creator-micro"):
                    successful_login = True
                    break
                    
                # 如果页面停留在登录页超过2分钟，提醒用户刷新页面
                if _ > 120 and page.url.startswith("https://creator.douyin.com/login"):
                    douyin_logger.warning("[+] 登录页面似乎卡住了，可能需要刷新页面...")
                    
                await asyncio.sleep(1)
                
            if successful_login:
                douyin_logger.success("[+] 登录成功，正在保存cookie...")
                await context.storage_state(path=account_file)
                douyin_logger.success(f"[+] cookie已保存到 {account_file}")
            else:
                douyin_logger.error("[+] 等待登录超时，请手动完成登录")
                
            await context.close()
            await browser.close()
        except Exception as e:
            douyin_logger.error(f"[+] 获取cookie过程出错: {str(e)}")


class DouYinVideo(object):
    def __init__(self, title, file_path, tags, publish_date: datetime, account_file, thumbnail_path=None):
        self.title = title  # 视频标题
        self.file_path = file_path
        self.tags = tags
        self.publish_date = publish_date
        self.account_file = account_file
        self.date_format = '%Y年%m月%d日 %H:%M'
        self.local_executable_path = LOCAL_CHROME_PATH
        self.thumbnail_path = thumbnail_path

    async def set_schedule_time_douyin(self, page, publish_date):
        # 选择包含特定文本内容的 label 元素
        label_element = page.locator("[class^='radio']:has-text('定时发布')")
        # 在选中的 label 元素下点击 checkbox
        await label_element.click()
        await asyncio.sleep(1)
        publish_date_hour = publish_date.strftime("%Y-%m-%d %H:%M")

        await asyncio.sleep(1)
        await page.locator('.semi-input[placeholder="日期和时间"]').click()
        await page.keyboard.press("Control+KeyA")
        await page.keyboard.type(str(publish_date_hour))
        await page.keyboard.press("Enter")

        await asyncio.sleep(1)

    async def handle_upload_error(self, page):
        douyin_logger.info('发现上传错误，尝试重新上传...')
        
        upload_success = False
        
        # 方法1: 如果有明确的重新上传按钮，点击它
        try:
            retry_button = page.locator("button:has-text('重新上传'), div:has-text('重新上传'):visible")
            if await retry_button.count() > 0:
                douyin_logger.info('找到重新上传按钮，点击中...')
                # 尝试使用文件选择器
                try:
                    async with page.expect_file_chooser() as fc_info:
                        await retry_button.click()
                    file_chooser = await fc_info.value
                    await file_chooser.set_files(self.file_path)
                    douyin_logger.info('通过文件选择器重新上传成功')
                    upload_success = True
                    return
                except Exception as e:
                    douyin_logger.warning(f'文件选择器方法失败: {str(e)}')
        except Exception as e:
            douyin_logger.warning(f'寻找重新上传按钮失败: {str(e)}')
        
        # 方法2: 直接寻找并设置文件输入元素
        if not upload_success:
            try:
                file_inputs = await page.locator('input[type="file"]').all()
                if file_inputs:
                    await file_inputs[0].set_input_files(self.file_path)
                    douyin_logger.info('通过直接设置文件输入重新上传成功')
                    upload_success = True
                    return
            except Exception as e:
                douyin_logger.warning(f'直接设置文件输入失败: {str(e)}')
        
        # 方法3: 使用JavaScript增强文件输入可见性再尝试
        if not upload_success:
            try:
                await page.evaluate("""
                () => {
                    document.querySelectorAll('input[type="file"]').forEach(input => {
                        input.removeAttribute('disabled');
                        input.removeAttribute('hidden');
                        input.setAttribute('style', 'opacity: 1; visibility: visible');
                    });
                }
                """)
                
                await page.locator('input[type="file"]').first.set_input_files(self.file_path)
                douyin_logger.info('通过JavaScript辅助重新上传成功')
                upload_success = True
                return
            except Exception as e:
                douyin_logger.error(f'JavaScript辅助方法失败: {str(e)}')
        
        if not upload_success:
            douyin_logger.error('所有重新上传方法均失败')
            # 截图以帮助调试
            await page.screenshot(path=f"reupload_fail_{datetime.now().strftime('%Y%m%d%H%M%S')}.png")
            # 我们不抛出异常，让流程继续，也许视频仍然可以发布

    async def wait_for_page_navigation(self, page, expected_urls, timeout=60, check_interval=1):
        """等待页面导航到预期URL之一，带有重试机制"""
        start_time = datetime.now()
        while (datetime.now() - start_time).total_seconds() < timeout:
            current_url = page.url
            for expected_url in expected_urls:
                if expected_url in current_url:
                    return True
            douyin_logger.info(f"  [-] 等待导航到预期页面，当前URL: {current_url}")
            await asyncio.sleep(check_interval)
        return False

    async def upload(self, playwright: Playwright) -> None:
        try:
            # 使用 Chromium 浏览器启动一个浏览器实例
            browser_args = ['--disable-blink-features=AutomationControlled']
            
            if self.local_executable_path:
                douyin_logger.info(f"  [-] 使用本地Chrome: {self.local_executable_path}")
                browser = await playwright.chromium.launch(
                    headless=False, 
                    executable_path=self.local_executable_path,
                    args=browser_args
                )
            else:
                browser = await playwright.chromium.launch(
                    headless=False,
                    args=browser_args
                )
                
            # 创建一个浏览器上下文，使用指定的 cookie 文件
            context = await browser.new_context(
                storage_state=f"{self.account_file}", 
                viewport={"width": 1280, "height": 800}
            )
            context = await set_init_script(context)

            # 创建一个新的页面
            page = await context.new_page()
            
            # 访问创作者中心首页，然后再导航到上传页面(提高成功率)
            douyin_logger.info(f'  [-] 正在打开抖音创作者中心...')
            await page.goto("https://creator.douyin.com/creator-micro/home", timeout=30000)
            await asyncio.sleep(3)  # 多等待一下
            
            douyin_logger.info(f'  [-] 正在导航到上传页面...')
            await page.goto("https://creator.douyin.com/creator-micro/content/upload", timeout=30000)
            await asyncio.sleep(2)  # 等待页面完全加载
            
            douyin_logger.info(f'[+] 正在上传视频: {self.title}.mp4')
            
            # 检查页面是否已经加载
            try:
                # 确认页面已加载
                await page.wait_for_selector("div.upload-btn, div.semi-upload, div:has-text('上传视频')", timeout=10000)
                douyin_logger.info(f"  [-] 已加载上传页面")
            except Exception as e:
                # 保存截图以供调试
                await page.screenshot(path="upload_page_error.png")
                douyin_logger.warning(f"  [-] 未找到标准上传区域: {str(e)}")
                # 尝试刷新页面
                await page.reload()
                await asyncio.sleep(5)
            
            # 优先使用直接设置文件输入的方法
            douyin_logger.info(f"  [-] 正在上传视频文件...")
            upload_success = False
            
            # 方法1 (优先): 直接设置文件输入，无需点击，最可靠的方法
            try:
                douyin_logger.info(f"  [-] 尝试直接设置文件输入...")
                file_inputs = await page.locator('input[type="file"]').all()
                if file_inputs:
                    await file_inputs[0].set_input_files(self.file_path)
                    douyin_logger.info(f"  [-] 文件路径已设置: {self.file_path}")
                    upload_success = True
                else:
                    douyin_logger.warning(f"  [-] 未找到文件输入元素")
            except Exception as e:
                douyin_logger.warning(f"  [-] 直接设置文件路径失败: {str(e)}")
            
            # 如果方法1失败，尝试方法2: 点击上传区域并使用文件选择器
            if not upload_success:
                try:
                    douyin_logger.info(f"  [-] 尝试点击上传区域...")
                    upload_button = page.locator("div.upload-btn, div.semi-upload, button:has-text('上传'), div:has-text('上传视频'):visible")
                    
                    if await upload_button.count() > 0:
                        douyin_logger.info(f"  [-] 找到上传按钮，正在点击...")
                        async with page.expect_file_chooser() as fc_info:
                            await upload_button.click()
                        file_chooser = await fc_info.value
                        # 直接设置完整路径，不需要浏览文件系统
                        await file_chooser.set_files(self.file_path)
                        douyin_logger.info(f"  [-] 文件路径已通过选择器设置: {self.file_path}")
                        upload_success = True
                except Exception as e:
                    douyin_logger.warning(f"  [-] 点击上传区域失败: {str(e)}")
            
            # 如果以上方法都失败，尝试方法3: 使用JavaScript直接操作DOM
            if not upload_success:
                try:
                    douyin_logger.info(f"  [-] 尝试使用JavaScript方法操作DOM...")
                    # 首先检查并列出页面上所有input[type="file"]元素
                    input_count = await page.evaluate("""() => {
                        const inputs = document.querySelectorAll('input[type="file"]');
                        return inputs.length;
                    }""")
                    
                    if input_count > 0:
                        douyin_logger.info(f"  [-] 找到 {input_count} 个文件输入元素，尝试设置第一个...")
                        # 通过JavaScript创建文件选择行为
                        # 注意：这里不使用click()，而是直接用JS修改文件输入属性
                        await page.evaluate("""
                        () => {
                            const input = document.querySelector('input[type="file"]');
                            // 移除可能阻止设置文件的属性
                            input.removeAttribute('disabled');
                            input.removeAttribute('hidden');
                            input.setAttribute('style', 'opacity: 1; visibility: visible');
                        }
                        """)
                        
                        # 再次尝试直接设置，因为我们已经通过JS修改了元素
                        await page.locator('input[type="file"]').first.set_input_files(self.file_path)
                        douyin_logger.info(f"  [-] 文件路径已通过JavaScript辅助设置: {self.file_path}")
                        upload_success = True
                    else:
                        douyin_logger.warning(f"  [-] 页面上没有找到文件输入元素")
                except Exception as e:
                    douyin_logger.error(f"  [-] JavaScript方法失败: {str(e)}")
            
            if not upload_success:
                # 所有方法都失败，保存更详细的页面信息以供调试
                await page.screenshot(path="all_upload_methods_failed.png")
                douyin_logger.error(f"  [-] 所有上传方法均失败，当前URL: {page.url}")
                # 输出页面上的所有按钮和输入元素以便调试
                buttons = await page.locator('button, div[role="button"]').all_text_contents()
                inputs = await page.locator('input').count()
                douyin_logger.info(f"  [-] 页面上找到 {inputs} 个输入元素和以下按钮: {buttons[:5]}")
                raise Exception("无法上传视频文件，所有方法均失败")
            
            douyin_logger.info(f'  [-] 文件已选择，等待上传并处理...')

            # 等待页面跳转到发布页面
            publish_page_urls = [
                "https://creator.douyin.com/creator-micro/content/publish",
                "https://creator.douyin.com/creator-micro/content/post/video"
            ]
            
            if not await self.wait_for_page_navigation(page, publish_page_urls, timeout=60):
                douyin_logger.error("  [-] 等待发布页面超时，尝试重新获取页面状态...")
                # 如果超时，尝试截图以便诊断
                await page.screenshot(path="douyin_navigation_timeout.png")
                douyin_logger.info(f"  [-] 已保存页面截图，当前URL: {page.url}")
                
                # 检查是否有错误提示
                if await page.locator("text=上传失败").count() > 0:
                    error_text = await page.locator("text=上传失败").all_text_contents()
                    douyin_logger.error(f"  [-] 检测到上传失败: {error_text}")
                
                if "content/publish" in page.url or "content/post/video" in page.url:
                    douyin_logger.info("  [-] 实际上已经进入发布页面，继续处理...")
                else:
                    raise Exception("导航到发布页面失败")
            
            # 填充标题和话题
            await asyncio.sleep(2)
            douyin_logger.info(f'  [-] 正在填充标题和话题...')
            
            # 尝试不同的标题输入方法
            try:
                title_container = page.get_by_text('作品标题').locator("..").locator("xpath=following-sibling::div[1]").locator("input")
                if await title_container.count():
                    await title_container.fill(self.title[:30])
                else:
                    titlecontainer = page.locator(".notranslate")
                    if await titlecontainer.count():
                        await titlecontainer.click()
                        await page.keyboard.press("Backspace")
                        await page.keyboard.press("Control+KeyA")
                        await page.keyboard.press("Delete")
                        await page.keyboard.type(self.title)
                        await page.keyboard.press("Enter")
                    else:
                        douyin_logger.warning("  [-] 找不到标题输入框，尝试其他定位方式...")
                        # 尝试其他定位方式
                        await page.locator("div[contenteditable='true']").fill(self.title[:30])
            except Exception as e:
                douyin_logger.error(f"  [-] 填充标题失败: {str(e)}")
            
            # 添加标签
            try:
                css_selector = ".zone-container"
                if await page.locator(css_selector).count() > 0:
                    for index, tag in enumerate(self.tags, start=1):
                        await page.type(css_selector, "#" + tag)
                        await page.press(css_selector, "Space")
                    douyin_logger.info(f'  [-] 已添加{len(self.tags)}个话题')
                else:
                    douyin_logger.warning("  [-] 找不到标签输入区域")
            except Exception as e:
                douyin_logger.error(f"  [-] 添加标签失败: {str(e)}")

            # 等待视频上传完成
            upload_timeout = 300  # 5分钟超时
            start_time = datetime.now()
            
            while (datetime.now() - start_time).total_seconds() < upload_timeout:
                try:
                    # 检查是否上传完成 - 使用多种方式检测
                    upload_done_selectors = [
                        '[class^="long-card"] div:has-text("重新上传")',
                        'div:has-text("上传完成")',
                        'div.upload-success',
                        'div:has-text("视频已上传")',
                        'div.progress-div:has(div.done)',
                        'div[role="progressbar"][aria-valuenow="100"]'
                    ]
                    
                    for selector in upload_done_selectors:
                        if await page.locator(selector).count() > 0:
                            douyin_logger.success(f"  [-] 视频上传完毕 (通过 {selector} 检测)")
                            await asyncio.sleep(1)  # 等待页面稳定
                            upload_done = True
                            break
                    else:  # 如果循环完成但没有break，则尝试继续等待
                        upload_done = False
                    
                    if upload_done:
                        break
                    
                    # 检查是否上传失败 - 使用多种方式检测
                    upload_failed_selectors = [
                        'div.progress-div > div:has-text("上传失败")',
                        'div:has-text("上传错误")',
                        'div.error-message:visible',
                        'div:has-text("重新上传"):not(:has-text("已上传"))'
                    ]
                    
                    for selector in upload_failed_selectors:
                        if await page.locator(selector).count() > 0:
                            douyin_logger.error(f"  [-] 检测到上传失败 (通过 {selector} 检测)，准备重试")
                            await self.handle_upload_error(page)
                            # 重置超时计时器，给重试更多时间
                            start_time = datetime.now()
                            break
                    
                    # 检查上传进度
                    progress_elements = await page.locator('div[role="progressbar"]').all()
                    if progress_elements:
                        try:
                            progress_value = await progress_elements[0].get_attribute("aria-valuenow")
                            if progress_value:
                                douyin_logger.info(f"  [-] 视频上传进度: {progress_value}%")
                        except:
                            pass
                    
                    douyin_logger.info("  [-] 正在上传视频中...")
                    await asyncio.sleep(3)
                except Exception as e:
                    douyin_logger.warning(f"  [-] 检查上传状态出错: {str(e)}")
                    await asyncio.sleep(3)
            
            if (datetime.now() - start_time).total_seconds() >= upload_timeout:
                # 即使超时也尝试继续，可能是检测逻辑问题但文件已经上传
                douyin_logger.warning("  [-] 视频上传检测超时，但尝试继续后续步骤")
                
                # 检查当前页面URL
                if any(url in page.url for url in ["content/publish", "content/post/video"]):
                    douyin_logger.info("  [-] 页面已处于发布状态，继续处理")
                else:
                    # 如果不在发布页面，再给一次机会
                    await asyncio.sleep(10)  # 多等待一会
                    if any(url in page.url for url in ["content/publish", "content/post/video"]):
                        douyin_logger.info("  [-] 页面现已处于发布状态，继续处理")
                    else:
                        douyin_logger.error("  [-] 视频上传可能失败，当前URL: " + page.url)
                        raise Exception("视频上传超时且不在发布页面")
            
            # 上传视频封面
            if self.thumbnail_path:
                douyin_logger.info(f'  [-] 正在上传封面...')
                await self.set_thumbnail(page, self.thumbnail_path)

            # 设置可见元素
            try:
                douyin_logger.info(f'  [-] 正在设置地理位置...')
                await self.set_location(page, "杭州市")
            except Exception as e:
                douyin_logger.warning(f"  [-] 设置地理位置失败: {str(e)}")

            # 头条/西瓜分发
            try:
                third_part_element = '[class^="info"] > [class^="first-part"] div div.semi-switch'
                if await page.locator(third_part_element).count():
                    if 'semi-switch-checked' not in await page.eval_on_selector(third_part_element, 'div => div.className'):
                        await page.locator(third_part_element).locator('input.semi-switch-native-control').click()
                        douyin_logger.info("  [-] 已启用第三方平台分发")
            except Exception as e:
                douyin_logger.warning(f"  [-] 设置第三方平台分发失败: {str(e)}")

            # 设置定时发布
            if self.publish_date != 0:
                douyin_logger.info(f'  [-] 正在设置定时发布: {self.publish_date}')
                await self.set_schedule_time_douyin(page, self.publish_date)

            # 点击发布并等待成功
            douyin_logger.info("  [-] 准备发布视频...")
            max_publish_attempts = 3
            publish_success = False
            
            for attempt in range(max_publish_attempts):
                try:
                    publish_button = page.get_by_role('button', name="发布", exact=True)
                    if await publish_button.count():
                        await publish_button.click()
                        
                    # 等待跳转到作品管理页面
                    await page.wait_for_url("https://creator.douyin.com/creator-micro/content/manage**", timeout=20000)
                    douyin_logger.success("  [-] 视频发布成功")
                    publish_success = True
                    break
                except Exception as e:
                    if attempt < max_publish_attempts - 1:
                        douyin_logger.warning(f"  [-] 发布尝试 {attempt+1}/{max_publish_attempts} 失败: {str(e)}")
                        await asyncio.sleep(3)
                    else:
                        douyin_logger.error(f"  [-] 多次尝试后发布失败: {str(e)}")
            
            if not publish_success:
                douyin_logger.error("  [-] 发布过程失败，但视频可能已保存为草稿")
                
            # 保存cookie并关闭浏览器
            await context.storage_state(path=self.account_file)
            douyin_logger.success('  [-] cookie更新完毕！')
            await asyncio.sleep(2)
            await context.close()
            await browser.close()
            
        except Exception as e:
            douyin_logger.error(f"  [-] 上传过程出现异常: {str(e)}")
            # 尝试截图
            try:
                await page.screenshot(path=f"douyin_error_{datetime.now().strftime('%Y%m%d%H%M%S')}.png")
                douyin_logger.info("  [-] 已保存错误截图")
            except:
                pass
            
            # 确保关闭浏览器
            try:
                await context.close()
                await browser.close()
            except:
                pass
            raise
    
    async def set_thumbnail(self, page: Page, thumbnail_path: str):
        if thumbnail_path:
            try:
                # 尝试点击选择封面按钮
                await page.click('text="选择封面"')
                await page.wait_for_selector("div.semi-modal-content:visible", timeout=5000)
                
                # 尝试设置竖封面
                try:
                    await page.click('text="设置竖封面"')
                    await page.wait_for_timeout(2000)
                except:
                    douyin_logger.warning("  [-] 无法找到'设置竖封面'按钮，继续上传...")
                
                # 定位到上传区域并选择文件
                file_input = page.locator("div[class^='semi-upload upload'] >> input.semi-upload-hidden-input")
                if await file_input.count():
                    await file_input.set_input_files(thumbnail_path)
                    await page.wait_for_timeout(3000)  # 等待上传
                    
                    # 点击完成按钮
                    complete_buttons = [
                        "div[class^='extractFooter'] button:visible:has-text('完成')",
                        "div[class^='confirmBtn'] >> div:has-text('完成')",
                        "div[class^='footer'] button:has-text('完成')"
                    ]
                    
                    for selector in complete_buttons:
                        if await page.locator(selector).count():
                            await page.locator(selector).click()
                            douyin_logger.info("  [-] 封面设置完成")
                            return
                    
                    douyin_logger.warning("  [-] 找不到完成按钮，尝试关闭弹窗...")
                    await page.press("Escape")  # 尝试按ESC关闭弹窗
                else:
                    douyin_logger.warning("  [-] 找不到封面上传输入框")
            except Exception as e:
                douyin_logger.error(f"  [-] 设置封面失败: {str(e)}")

    async def set_location(self, page: Page, location: str = "杭州市"):
        try:
            # 先检查是否有地理位置输入框
            location_selector = 'div.semi-select span:has-text("输入地理位置")'
            
            if await page.locator(location_selector).count():
                await page.locator(location_selector).click()
                await page.keyboard.press("Backspace")
                await page.wait_for_timeout(2000)
                await page.keyboard.type(location)
                
                # 等待并选择位置选项
                try:
                    await page.wait_for_selector('div[role="listbox"] [role="option"]', timeout=5000)
                    await page.locator('div[role="listbox"] [role="option"]').first.click()
                    douyin_logger.info(f"  [-] 已设置地理位置: {location}")
                except:
                    douyin_logger.warning(f"  [-] 等待位置选项超时")
            else:
                douyin_logger.info(f"  [-] 找不到地理位置输入框，跳过设置")
        except Exception as e:
            douyin_logger.warning(f"  [-] 设置地理位置时出错: {str(e)}")

    async def main(self):
        async with async_playwright() as playwright:
            await self.upload(playwright)


