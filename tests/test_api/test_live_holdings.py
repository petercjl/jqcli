import copy
import pytest
import httpx
from jqcli.api.client import ApiClient
from jqcli.api.live_holdings import reconstruct, get_live_transactions, get_live_holdings
from jqcli.errors import ApiError


def inputs():
    s = {'id':'demo','cash':10000,'is_limit':False,'positions':[
        {'code':'510300.XSHG','name':'示例ETF','asset_type':'基金','side':'多','amount':'100股','time':'2026-01-06 09:05:00'},
        {'code':'510300.XSHG','name':'示例ETF','asset_type':'基金','side':'多','amount':'200股','time':'2026-01-06 09:05:00'}]}
    t = {'date':'2026-01-06','complete':True,'queried_at':'2026-01-06T10:00:00+08:00','transactions':[
        {'code':'000001.XSHE','name':'示例股','side':'买','filled_quantity':100,'filled_value':1000,'commission':5,
         'order_quantity':100,'status':'全部成交','order_time':'2026-01-06 09:40:00','match_time':'2026-01-06 09:41:00'}]}
    return s,t


def test_aggregate_buy_and_cash_no_stale_valuation():
    r=reconstruct(*inputs())
    assert [x['quantity'] for x in r['positions']]==[300,100]
    assert r['reconstructed_cash']==8995
    assert r['cash'] is None and r['total_value'] is None
    assert all(x['weight'] is None and x['closeable_amount'] is None for x in r['positions'])


def test_sell_and_remove_empty_position():
    s,t=inputs(); t['transactions'][0].update(code='510300.XSHG',name='示例ETF',side='卖',filled_quantity=300,order_quantity=300)
    r=reconstruct(s,t)
    assert r['positions']==[] and r['reconstructed_cash']==10995


@pytest.mark.parametrize('case',['partial','truncated','boundary','duplicate','wrong_date','empty','negative','nonfinite','unknown_side','bad_time'])
def test_ambiguous_data_fails_closed(case):
    s,t=inputs(); row=t['transactions'][0]
    if case=='partial': row['status']='部分成交'
    if case=='truncated': t['complete']=False
    if case=='boundary': row['order_time']='2026-01-06 09:05:00'
    if case=='duplicate': t['transactions'].append(copy.deepcopy(row))
    if case=='wrong_date': t['date']='2026-01-07'
    if case=='empty': s['positions']=[]
    if case=='negative': row['side']='卖'
    if case=='nonfinite': s['cash']='NaN'
    if case=='unknown_side': row['side']='申购'
    if case=='bad_time': row['match_time']='unknown'
    with pytest.raises(ApiError): reconstruct(s,t)


def page(side='卖', amount="<span class='sell'>-300股</span>", total=-2565.6):
    return {'name':'示例模拟盘','url':'https://www.joinquant.com/algorithm/live/index?backtestId=demo',
        'read_at':'2026-01-06T10:00:00+08:00','dates':['下单详情(2026-01-06)'],
        'transactions':{'records':1,'rows':[{'stock':'示例ETF(510300.XSHG)','security':'基金',
        'date':'2026-01-06','time':'09:40:00','amount':amount,'orderAmount':amount,'total':total,
        'commission':5,'transaction':side,'status':'全部成交','matchTime':'2026-01-06 09:41:00'}]}}


def test_page_sell_signed_values_and_no_api(monkeypatch):
    monkeypatch.setattr('jqcli.api.live_holdings.read_live_page',lambda *a:page())
    # No ApiClient methods exist; any endpoint fallback fails this test.
    r=get_live_transactions(object(),'demo',date='2026-01-06',source='page')
    assert r['source']=='live_page_transaction_table'
    assert r['transactions'][0]['filled_quantity']==300
    assert r['transactions'][0]['filled_value']==2565.6
    s,_=inputs(); out=reconstruct(s,r)
    assert out['positions']==[] and out['reconstructed_cash']==12560.6


def test_page_wrong_sign_rejected(monkeypatch):
    monkeypatch.setattr('jqcli.api.live_holdings.read_live_page',lambda *a:page(side='买'))
    with pytest.raises(ApiError,match='SIGN_MISMATCH'):get_live_transactions(object(),'demo',date='2026-01-06',source='page')


def test_page_date_and_truncation(monkeypatch):
    monkeypatch.setattr('jqcli.api.live_holdings.read_live_page',lambda *a:page())
    with pytest.raises(ApiError,match='DATE_MISMATCH'):get_live_transactions(object(),'demo',date='2026-01-07',source='page')
    d=page();d['transactions']['records']=2
    monkeypatch.setattr('jqcli.api.live_holdings.read_live_page',lambda *a:d)
    with pytest.raises(ApiError,match='INCOMPLETE'):get_live_transactions(object(),'demo',date='2026-01-06',source='page')


def test_holdings_reads_both_tables_once(monkeypatch):
    d=page();d['cash']='￥10,000';d['positions']={'records':1,'rows':[{
        'stock':'示例ETF(510300.XSHG)','security':'基金','side':'多','amount':'500股','time':'2026-01-06 09:05:00'}]}
    calls=[]
    def read(*args):calls.append(args);return d
    monkeypatch.setattr('jqcli.api.live_holdings.read_live_page',read)
    out=get_live_holdings(object(),'demo',date='2026-01-06',name='示例模拟盘',source='page')
    assert len(calls)==1 and out['positions'][0]['quantity']==200
    assert out['reconstructed_cash']==12560.6 and out['total_value'] is None


def test_fills_before_updated_snapshot_are_not_replayed():
    s,t=inputs()
    for row in s['positions']:row['time']='2026-01-06 11:30:00'
    out=reconstruct(s,t)
    assert out['applied_fill_count']==0 and out['reconstructed_cash']==10000


def test_two_times_same_security_both_count():
    s,t=inputs();r=copy.deepcopy(t['transactions'][0]);r['order_time']='2026-01-06 09:42:00';r['match_time']='2026-01-06 09:42:00';t['transactions'].append(r)
    out=reconstruct(s,t)
    assert out['positions'][1]['quantity']==200 and out['applied_fill_count']==2
