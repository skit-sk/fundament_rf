from flask import Blueprint, request, jsonify, render_template
from infographics import DashboardKPI, EquityAnalyzer, CalendarHeatmap, DashboardCharts, SVGDashboard
from infographics.svg import get_mini_color, get_roe_color
from calendar import monthrange

bp = Blueprint('dashboard', __name__, url_prefix='/dashboard')

kpi_engine = DashboardKPI()
equity_engine = EquityAnalyzer()
calendar_engine = CalendarHeatmap()
charts_engine = DashboardCharts()


def generate_heatmap_html(heatmap_data: dict) -> str:
    """Generate HTML for heatmap with mini-cells (Variant 1)."""
    symbols = heatmap_data.get('y', [])
    months = heatmap_data.get('x', [])
    cells = heatmap_data.get('cells', {})
    symbol_min = heatmap_data.get('symbol_min', {})
    symbol_max = heatmap_data.get('symbol_max', {})

    if not symbols or not months:
        return '<div class="heatmap-empty">No data</div>'

    html = '<div class="heatmap-var1-grid">'

    html += '<div class="heatmap-var1-row heatmap-header-row">'
    html += '<div class="heatmap-label-cell"></div>'
    for month in months:
        html += f'<div class="heatmap-month-cell">{month}</div>'
    html += '</div>'

    for symbol in symbols:
        html += '<div class="heatmap-var1-row">'
        html += f'<div class="heatmap-label-cell">{symbol}</div>'
        sym_cells = cells.get(symbol, {})
        min_roe = symbol_min.get(symbol, 0)
        max_roe = symbol_max.get(symbol, 1)
        for month in months:
            days = sym_cells.get(month, [])
            html += '<div class="heatmap-cell">'
            if days:
                for day in days:
                    color = get_mini_color(day['roe_pct'], min_roe, max_roe)
                    html += f'<div class="mini-cell" style="background:{color}" title="{day["date"]}: {day["roe_pct"]}%"></div>'
            html += '</div>'
        html += '</div>'

    html += '</div>'
    return html


def generate_stacked_heatmap_html(heatmap_data: dict) -> str:
    """Generate HTML for heatmap with stacked bars (1 segment = 1 day)."""
    symbols = heatmap_data.get('y', [])
    months = heatmap_data.get('x', [])
    cells = heatmap_data.get('cells', {})

    if not symbols or not months:
        return '<div class="heatmap-empty">No data</div>'

    html = '<div class="stacked-heatmap">'

    html += '<div class="stacked-header-row">'
    html += '<div class="stacked-label-col"></div>'
    for month in months:
        year, mon = month.split('-')
        days_in_month = monthrange(int(year), int(mon))[1]
        html += f'<div class="stacked-month-col">{month}<span class="stacked-days-count">{days_in_month}d</span></div>'
    html += '</div>'

    for symbol in symbols:
        html += '<div class="stacked-row">'
        html += f'<div class="stacked-label-col">{symbol}</div>'
        sym_cells = cells.get(symbol, {})
        for month in months:
            year, mon = month.split('-')
            days_in_month = monthrange(int(year), int(mon))[1]
            days = sym_cells.get(month, [])
            html += f'<div class="stacked-bar-col" data-days="{days_in_month}">'
            html += '<div class="stacked-bar">'
            days_dict = {d['date']: d for d in days}
            for d in range(1, days_in_month + 1):
                day_str = f'{year}-{mon}-{d:02d}'
                if day_str in days_dict:
                    roe = days_dict[day_str]['roe_pct']
                    pnl = days_dict[day_str].get('pnl_usdt', 0)
                    color = get_roe_color(roe)
                    html += f'<div class="stacked-segment" style="background:{color}" title="{day_str}: ROE {roe:+.1f}%, PnL {pnl:+.2f} USDT"></div>'
                else:
                    color = '#d1d5db'
                    html += f'<div class="stacked-segment" style="background:{color}" title="{day_str}: No trade"></div>'
            html += '</div></div>'
        html += '</div>'

    html += '</div>'
    return html


@bp.route('/')
def index():
    summary = kpi_engine.get_summary()
    donut = kpi_engine.get_donut()
    distribution = kpi_engine.get_distribution()
    by_symbol = kpi_engine.get_pnl_by_symbol()
    equity_data = equity_engine.get_equity_curve()
    heatmap_data = equity_engine.get_heatmap_data()
    top_trades = kpi_engine.get_top_trades(limit=3)

    months = heatmap_data.get('x', [])
    cal_year, cal_month = 2026, 4
    if months:
        last_month = months[-1]
        cal_year, cal_month = int(last_month.split('-')[0]), int(last_month.split('-')[1])
    calendar_data = calendar_engine.get_month_data(cal_year, cal_month)

    equity_chart = charts_engine.equity_drawdown_chart(equity_data)
    distribution_chart = charts_engine.pnl_distribution_bars(distribution)
    by_symbol_chart = charts_engine.pnl_by_symbol_chart(by_symbol)
    heatmap_chart = charts_engine.heatmap_chart(heatmap_data)
    donut_svg = SVGDashboard.donut_chart(donut['win'], donut['loss'])
    heatmap_var1_html = generate_stacked_heatmap_html(heatmap_data)

    return render_template('dashboard.html',
        kpi=summary,
        donut={'win': donut['win'], 'loss': donut['loss'], 'svg': donut_svg},
        distribution=distribution,
        distribution_chart=distribution_chart,
        by_symbol=by_symbol,
        by_symbol_chart=by_symbol_chart,
        equity_data=equity_data,
        equity_chart=equity_chart,
        heatmap_data=heatmap_data,
        heatmap_chart=heatmap_chart,
        heatmap_var1_html=heatmap_var1_html,
        top_trades=top_trades,
        calendar_data=calendar_data
    )


@bp.route('/api/kpi')
def api_kpi():
    summary = kpi_engine.get_summary()
    return jsonify(summary)


@bp.route('/api/donut')
def api_donut():
    donut = kpi_engine.get_donut()
    svg = SVGDashboard.donut_chart(donut['win'], donut['loss'])
    return jsonify({'win': donut['win'], 'loss': donut['loss'], 'svg': svg})


@bp.route('/api/distribution')
def api_distribution():
    dist = kpi_engine.get_distribution()
    chart_html = charts_engine.pnl_distribution_bars(dist)
    return jsonify({'distribution': dist, 'chart': chart_html})


@bp.route('/api/by_symbol')
def api_by_symbol():
    by_symbol = kpi_engine.get_pnl_by_symbol()
    chart_html = charts_engine.pnl_by_symbol_chart(by_symbol)
    return jsonify({'by_symbol': by_symbol, 'chart': chart_html})


@bp.route('/api/equity')
def api_equity():
    equity_data = equity_engine.get_equity_curve()
    chart_html = charts_engine.equity_drawdown_chart(equity_data)
    return jsonify({'equity': equity_data, 'chart': chart_html})


@bp.route('/api/heatmap')
def api_heatmap():
    heatmap_data = equity_engine.get_heatmap_data()
    chart_html = charts_engine.heatmap_chart(heatmap_data)
    return jsonify({'heatmap': heatmap_data, 'chart': chart_html})


@bp.route('/api/top_trades')
def api_top_trades():
    top_trades = kpi_engine.get_top_trades(limit=3)
    return jsonify(top_trades)


@bp.route('/api/calendar')
def api_calendar():
    year = request.args.get('year', type=int)
    month = request.args.get('month', type=int)
    if not year or not month:
        from datetime import datetime
        now = datetime.now()
        year = now.year
        month = now.month
    data = calendar_engine.get_month_data(year, month)
    return jsonify(data)


@bp.route('/api/all')
def api_all():
    summary = kpi_engine.get_summary()
    donut = kpi_engine.get_donut()
    distribution = kpi_engine.get_distribution()
    by_symbol = kpi_engine.get_pnl_by_symbol()
    equity_data = equity_engine.get_equity_curve()
    heatmap_data = equity_engine.get_heatmap_data()
    top_trades = kpi_engine.get_top_trades(limit=3)

    equity_chart = charts_engine.equity_drawdown_chart(equity_data)
    distribution_chart = charts_engine.pnl_distribution_bars(distribution)
    by_symbol_chart = charts_engine.pnl_by_symbol_chart(by_symbol)
    heatmap_chart = charts_engine.heatmap_chart(heatmap_data)
    donut_svg = SVGDashboard.donut_chart(donut['win'], donut['loss'])

    return jsonify({
        'kpi': summary,
        'donut': {'win': donut['win'], 'loss': donut['loss'], 'svg': donut_svg},
        'distribution': distribution,
        'distribution_chart': distribution_chart,
        'by_symbol': by_symbol,
        'by_symbol_chart': by_symbol_chart,
        'equity': equity_data,
        'equity_chart': equity_chart,
        'heatmap': heatmap_data,
        'heatmap_chart': heatmap_chart,
        'top_trades': top_trades
    })
