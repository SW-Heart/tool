"""
命令行工具
ETF数据爬取和查询CLI
"""
import click
import logging
from datetime import datetime
from tabulate import tabulate

import sys
sys.path.insert(0, str(__file__).rsplit('/', 2)[0])
from etf_scraper.scraper.base import get_scraper
from etf_scraper.storage.database import Database
from config import ETF_TICKERS

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@click.group()
def cli():
    """Farside ETF 数据爬虫工具"""
    pass


@cli.command()
@click.argument('etf_type', type=click.Choice(['btc', 'eth', 'sol']))
@click.option('--headless/--no-headless', default=True, help='是否使用无头模式')
def scrape(etf_type: str, headless: bool):
    """
    爬取ETF数据
    
    ETF_TYPE: btc, eth, sol
    """
    click.echo(f"正在爬取 {etf_type.upper()} ETF 数据...")
    
    try:
        scraper = get_scraper(etf_type)
        flows = scraper.scrape(headless=headless, save=True)
        
        click.echo(click.style(f"✓ 成功爬取 {len(flows)} 条数据", fg='green'))
        
        if flows:
            # 显示最新几条
            click.echo("\n最新数据:")
            _display_flows(flows[:5])
            
    except Exception as e:
        click.echo(click.style(f"✗ 爬取失败: {e}", fg='red'))
        raise


@cli.command()
@click.argument('etf_type', type=click.Choice(['btc', 'eth', 'sol']))
@click.option('--days', '-d', default=15, help='查询天数')
def list(etf_type: str, days: int):
    """
    列出ETF历史数据
    
    ETF_TYPE: btc, eth, sol
    """
    db = Database()
    flows = db.get_daily_flows(etf_type, days)
    
    if not flows:
        click.echo(click.style("暂无数据，请先执行 scrape 命令爬取数据", fg='yellow'))
        return
    
    click.echo(f"\n{etf_type.upper()} ETF 最近 {len(flows)} 天数据:\n")
    _display_flows(flows)


@cli.command()
@click.argument('etf_type', type=click.Choice(['btc', 'eth', 'sol']))
@click.argument('date')
def date(etf_type: str, date: str):
    """
    按日期查询ETF数据
    
    ETF_TYPE: btc, eth, sol
    DATE: YYYY-MM-DD 格式的日期
    """
    # 验证日期格式
    try:
        datetime.strptime(date, "%Y-%m-%d")
    except ValueError:
        click.echo(click.style("日期格式错误，请使用 YYYY-MM-DD", fg='red'))
        return
    
    db = Database()
    flow = db.get_flow_by_date(etf_type, date)
    
    if not flow:
        click.echo(click.style(f"未找到 {date} 的数据", fg='yellow'))
        return
    
    click.echo(f"\n{etf_type.upper()} ETF {date} 数据:\n")
    
    # 显示汇总
    click.echo(f"日期: {flow.date}")
    click.echo(f"总流入: {_format_flow(flow.total_flow)} 百万美元")
    
    # 显示各机构
    if flow.ticker_flows:
        click.echo("\n各机构明细:")
        table_data = []
        for ticker, amount in sorted(flow.ticker_flows.items(), key=lambda x: x[1], reverse=True):
            table_data.append([ticker, _format_flow(amount)])
        
        click.echo(tabulate(table_data, headers=['机构', '流入(百万美元)'], tablefmt='simple'))


@cli.command()
@click.argument('etf_type', type=click.Choice(['btc', 'eth', 'sol']))
@click.argument('ticker')
@click.option('--days', '-d', default=30, help='查询天数')
def ticker(etf_type: str, ticker: str, days: int):
    """
    按机构查询ETF数据
    
    ETF_TYPE: btc, eth, sol
    TICKER: 机构代码 (如 IBIT, FBTC)
    """
    ticker = ticker.upper()
    
    # 验证机构代码
    valid_tickers = ETF_TICKERS.get(etf_type, [])
    if ticker not in valid_tickers:
        click.echo(click.style(f"无效的机构代码，可用的机构: {', '.join(valid_tickers)}", fg='yellow'))
        return
    
    db = Database()
    flows = db.get_flows_by_ticker(etf_type, ticker, days)
    
    if not flows:
        click.echo(click.style(f"未找到机构 {ticker} 的数据", fg='yellow'))
        return
    
    click.echo(f"\n{etf_type.upper()} ETF - {ticker} 最近 {len(flows)} 天数据:\n")
    
    table_data = []
    total = 0
    for f in flows:
        table_data.append([f['date'], _format_flow(f['flow_usd'])])
        total += f['flow_usd']
    
    click.echo(tabulate(table_data, headers=['日期', '流入(百万美元)'], tablefmt='simple'))
    click.echo(f"\n累计: {_format_flow(total)} 百万美元")


@cli.command()
@click.argument('etf_type', type=click.Choice(['btc', 'eth', 'sol']))
def summary(etf_type: str):
    """
    显示ETF汇总统计
    
    ETF_TYPE: btc, eth, sol
    """
    db = Database()
    s = db.get_summary(etf_type)
    
    if not s.trading_days:
        click.echo(click.style("暂无数据，请先执行 scrape 命令爬取数据", fg='yellow'))
        return
    
    click.echo(f"\n{etf_type.upper()} ETF 汇总统计:\n")
    click.echo(f"数据范围: {s.start_date} ~ {s.end_date}")
    click.echo(f"交易天数: {s.trading_days}")
    click.echo(f"总流入: {_format_flow(s.total_inflow)} 百万美元")
    click.echo(f"总流出: {_format_flow(s.total_outflow)} 百万美元")
    click.echo(f"净流入: {_format_flow(s.net_flow)} 百万美元")
    click.echo(f"日均流入: {_format_flow(s.avg_daily_flow)} 百万美元")
    
    # 各机构排名
    if s.ticker_totals:
        click.echo("\n各机构累计流入排名:")
        table_data = []
        for ticker, amount in sorted(s.ticker_totals.items(), key=lambda x: x[1], reverse=True):
            table_data.append([ticker, _format_flow(amount)])
        
        click.echo(tabulate(table_data, headers=['机构', '累计流入(百万美元)'], tablefmt='simple'))


@cli.command()
@click.option('--host', default='0.0.0.0', help='服务器地址')
@click.option('--port', default=8000, help='服务器端口')
def serve(host: str, port: int):
    """启动API服务"""
    click.echo(f"启动API服务: http://{host}:{port}")
    
    from etf_scraper.api.server import run_server
    run_server(host=host, port=port)


@cli.command()
@click.option('--etf', '-e', multiple=True, 
              type=click.Choice(['btc', 'eth', 'sol']), help='要爬取的ETF类型')
@click.option('--all', 'all_etf', is_flag=True, help='爬取所有ETF类型(btc/eth/sol)')
@click.option('--now', is_flag=True, help='立即执行一次爬取')
def scheduler(etf, all_etf, now):
    """
    启动定时爬取调度器
    
    每天 00:00, 06:00, 12:00, 18:00 自动爬取
    
    示例:
      python cli.py scheduler --all --now
      python cli.py scheduler -e btc -e eth --now
    """
    from scheduler.cron import ETFScheduler
    
    # 确定要爬取的ETF类型
    if all_etf:
        etf_types = ['btc', 'eth', 'sol']
    elif etf:
        etf_types = list(etf)
    else:
        etf_types = ['btc']  # 默认只爬BTC
    
    click.echo("=" * 50)
    click.echo("ETF 定时爬取调度器")
    click.echo("=" * 50)
    click.echo(f"爬取类型: {', '.join([e.upper() for e in etf_types])}")
    click.echo("定时计划:")
    click.echo("  - 每天 00:00")
    click.echo("  - 每天 06:00")
    click.echo("  - 每天 12:00")
    click.echo("  - 每天 18:00")
    click.echo("=" * 50)
    
    if now:
        click.echo("将立即执行一次爬取...")
    
    click.echo("按 Ctrl+C 停止调度器\n")
    
    sched = ETFScheduler(etf_types)
    sched.run(run_immediately=now)


def _display_flows(flows):
    """显示流入数据表格"""
    if not flows:
        return
    
    # 获取所有机构代码
    all_tickers = set()
    for f in flows:
        all_tickers.update(f.ticker_flows.keys())
    
    tickers = sorted(all_tickers)
    
    # 构建表格
    headers = ['日期'] + tickers + ['总计']
    table_data = []
    
    for f in flows:
        row = [f.date]
        for ticker in tickers:
            row.append(_format_flow(f.ticker_flows.get(ticker, 0)))
        row.append(_format_flow(f.total_flow))
        table_data.append(row)
    
    click.echo(tabulate(table_data, headers=headers, tablefmt='simple'))


def _format_flow(value: float) -> str:
    """格式化流入值"""
    if value == 0:
        return "-"
    elif value > 0:
        return f"{value:.1f}"
    else:
        return click.style(f"({abs(value):.1f})", fg='red')


if __name__ == '__main__':
    cli()
