import plotly.graph_objects as go
from plotly.subplots import make_subplots
from typing import Dict, Any, List, Optional


class DashboardCharts:
    def __init__(self):
        self.template = 'plotly_dark'

    def equity_drawdown_chart(self, equity_data: Dict[str, Any]) -> str:
        equity_curve = equity_data.get('equity_curve', [])
        drawdown_curve = equity_data.get('drawdown_curve', [])

        if not equity_curve:
            return self._empty_chart('No equity data')

        dates = [e['date'] for e in equity_curve]
        cumulative = [e['cumulative_pnl'] for e in equity_curve]
        drawdown_pcts = [d['drawdown_pct'] for d in drawdown_curve]

        fig = make_subplots(specs=[[{'secondary_y': True}]])

        fig.add_trace(
            go.Scatter(
                x=dates,
                y=cumulative,
                mode='lines',
                name='Cumulative PnL (USDT)',
                line=dict(color='#3b82f6', width=2),
                fill='tozeroy',
                fillcolor='rgba(59, 130, 246, 0.1)'
            ),
            secondary_y=False
        )

        fig.add_trace(
            go.Scatter(
                x=dates,
                y=drawdown_pcts,
                mode='lines',
                name='Drawdown (%)',
                line=dict(color='#ef4444', width=1, dash='dot'),
                fill='tozeroy',
                fillcolor='rgba(239, 68, 68, 0.1)'
            ),
            secondary_y=True
        )

        fig.update_layout(
            template=self.template,
            height=350,
            margin=dict(l=60, r=60, t=30, b=60),
            legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1),
            hovermode='x unified'
        )
        fig.update_xaxes(title_text='Date', tickangle=-45, nticks=10)
        fig.update_yaxes(title_text='PnL (USDT)', secondary_y=False, tickformat='+.2f')
        fig.update_yaxes(title_text='Drawdown %', secondary_y=True, tickformat='.1f%', side='right')

        return fig.to_html(full_html=False, include_plotlyjs=False)

    def pnl_distribution_bars(self, distribution: List[Dict[str, Any]]) -> str:
        if not distribution:
            return self._empty_chart('No distribution data')

        distribution = sorted(distribution, key=lambda x: x['pnl_usdt'])
        names = [d['name'][:15] for d in distribution]
        pnl_values = [d['pnl_usdt'] for d in distribution]
        colors = ['#22c55e' if p >= 0 else '#ef4444' for p in pnl_values]

        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=names,
            y=pnl_values,
            marker_color=colors,
            text=[f'{p:+.2f}' for p in pnl_values],
            textposition='inside',
            insidetextanchor='middle',
            textfont=dict(color='white', size=8)
        ))

        fig.update_layout(
            template=self.template,
            height=280,
            margin=dict(l=40, r=40, t=30, b=80),
            xaxis_title='Trade',
            yaxis_title='PnL (USDT)',
            showlegend=False,
            xaxis=dict(tickangle=-45, tickfont=dict(size=9))
        )

        return fig.to_html(full_html=False, include_plotlyjs=False)

    def pnl_by_symbol_chart(self, by_symbol: Dict[str, Dict[str, float]]) -> str:
        if not by_symbol:
            return self._empty_chart('No symbol data')

        symbols = sorted(by_symbol.keys())
        pnl_values = [by_symbol[s]['pnl_usdt'] for s in symbols]
        colors = ['#22c55e' if p >= 0 else '#ef4444' for p in pnl_values]

        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=symbols,
            y=pnl_values,
            marker_color=colors,
            text=[f'{p:+.2f}' for p in pnl_values],
            textposition='inside',
            insidetextanchor='middle',
            textfont=dict(color='white', size=8)
        ))

        fig.update_layout(
            template=self.template,
            height=280,
            margin=dict(l=50, r=50, t=30, b=50),
            xaxis_title='Symbol',
            yaxis_title='Total PnL (USDT)',
            showlegend=False
        )

        return fig.to_html(full_html=False, include_plotlyjs=False)

    def heatmap_chart(self, heatmap_data: Dict[str, Any]) -> str:
        z = heatmap_data.get('z', [])
        x = heatmap_data.get('x', [])
        y = heatmap_data.get('y', [])
        symbol_min = heatmap_data.get('symbol_min', {})
        symbol_max = heatmap_data.get('symbol_max', {})

        if not z or not x or not y:
            return self._empty_chart('No heatmap data')

        z_normalized = []
        for sym_idx, sym in enumerate(y):
            row = []
            min_roe = symbol_min.get(sym, 0)
            max_roe = symbol_max.get(sym, 1)
            range_roe = max_roe - min_roe if max_roe != min_roe else 1
            for val in z[sym_idx]:
                if val == 0:
                    row.append(0.5)
                else:
                    normalized = (val - min_roe) / range_roe
                    row.append(normalized)
            z_normalized.append(row)

        fig = go.Figure(data=go.Heatmap(
            z=z_normalized,
            x=x,
            y=y,
            colorscale=[
                [0.0, 'rgb(220, 38, 38)'],
                [0.25, 'rgb(239, 68, 68)'],
                [0.4, 'rgb(252, 165, 165)'],
                [0.5, 'rgb(156, 163, 175)'],
                [0.6, 'rgb(134, 239, 172)'],
                [0.75, 'rgb(34, 197, 94)'],
                [1.0, 'rgb(22, 163, 74)']
            ],
            zmin=0,
            zmax=1,
            text=[[f'{v:+.1f}%' for v in row] for row in z],
            texttemplate='%{text}',
            textfont=dict(size=9, color='white'),
            hovertemplate='Symbol: %{y}<br>Month: %{x}<br>Avg ROE: %{text}<extra></extra>'
        ))

        fig.update_layout(
            template=self.template,
            height=300,
            margin=dict(l=80, r=30, t=30, b=50),
            xaxis_title='Month',
            yaxis_title='Symbol'
        )

        return fig.to_html(full_html=False, include_plotlyjs=False)

    def _empty_chart(self, message: str) -> str:
        fig = go.Figure()
        fig.add_annotation(
            text=message,
            x=0.5, y=0.5,
            xref='paper', yref='paper',
            show=False,
            font=dict(size=14, color='gray')
        )
        fig.update_layout(
            template=self.template,
            height=200,
            xaxis=dict(visible=False),
            yaxis=dict(visible=False)
        )
        return fig.to_html(full_html=False, include_plotlyjs=False)
