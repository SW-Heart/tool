"""
Farside ETF 爬虫服务器
主入口文件
"""
import click
import logging

from etf_scraper.scraper.base import get_scraper, BTCScraper, ETHScraper, SOLScraper
from etf_scraper.storage.database import Database
from etf_scraper.api.server import app, run_server
from config import API_CONFIG, LOG_CONFIG

# 配置日志
logging.basicConfig(
    level=getattr(logging, LOG_CONFIG["level"]),
    format=LOG_CONFIG["format"],
)
logger = logging.getLogger(__name__)


def scrape_all():
    """爬取所有ETF数据"""
    etf_types = ['btc', 'eth', 'sol']
    
    for etf_type in etf_types:
        try:
            logger.info(f"开始爬取 {etf_type.upper()} ETF 数据")
            scraper = get_scraper(etf_type)
            flows = scraper.scrape()
            logger.info(f"成功爬取 {len(flows)} 条 {etf_type.upper()} 数据")
        except Exception as e:
            logger.error(f"爬取 {etf_type.upper()} 失败: {e}")


@click.group()
def main():
    """Farside ETF 爬虫服务器"""
    pass


@main.command()
@click.option('--host', default=API_CONFIG["host"], help='服务器地址')
@click.option('--port', default=API_CONFIG["port"], help='服务器端口')
def serve(host: str, port: int):
    """启动API服务"""
    logger.info(f"启动API服务: http://{host}:{port}")
    run_server(host=host, port=port)


@main.command()
@click.argument('etf_type', type=click.Choice(['btc', 'eth', 'sol', 'all']))
@click.option('--headless/--no-headless', default=True, help='是否使用无头模式')
def scrape(etf_type: str, headless: bool):
    """爬取ETF数据"""
    if etf_type == 'all':
        scrape_all()
    else:
        try:
            scraper = get_scraper(etf_type)
            flows = scraper.scrape(headless=headless)
            logger.info(f"成功爬取 {len(flows)} 条数据")
        except Exception as e:
            logger.error(f"爬取失败: {e}")


@main.command()
def init():
    """初始化数据库"""
    db = Database()
    logger.info("数据库初始化完成")


if __name__ == '__main__':
    main()
