"""Direct HTTP contract: no browser access, strict completeness and stable reads."""
import copy
import pytest
from jqcli.api.live_holdings import get_live_transactions, get_live_holdings
from jqcli.errors import ApiError

DATE = '2026-01-06'

def payload(rows=None):
    return {'data': {'transaction': rows or [], 'isLimit': False}, 'code': '00000', 'status': '0'}

def row():
    return {'stock':'示例ETF(510300.XSHG)','security':'基金','date':DATE,
        'time':'09:40:00','amount':"<span>-100股</span>",'orderAmount':'-100股',
        'total':-1000,'commission':5,'transaction':'卖','status':'全部成交',
        'matchTime':DATE+' 09:40:00'}

class Client:
    def __init__(self, data): self.data=data; self.calls=[]
    def get(self, path, **kw):
        self.calls.append((path,kw))
        return copy.deepcopy(self.data)

def test_transactions_direct_without_browser(monkeypatch):
    monkeypatch.setattr('jqcli.api.live_holdings.read_live_page', lambda *a: pytest.fail('browser used'))
    c=Client(payload([row()]))
    out=get_live_transactions(c,'resolved',date=DATE)
    assert c.calls[0][0]=='/algorithm/live/transactionDetail'
    assert c.calls[0][1]['params']['backtestId']=='resolved'
    assert out['source']=='live_transaction_api' and out['complete']
    assert out['transactions'][0]['filled_quantity']==100
    assert out['transactions'][0]['commission']==5

def test_empty_day_is_complete_only_with_explicit_envelope():
    assert get_live_transactions(Client(payload()),'demo',date=DATE)['transactions']==[]

@pytest.mark.parametrize('bad',[{}, {'data':{}}, {'data':{'transaction':[], 'isLimit':True}},
    {'data':{'transaction':[]}}, {'data':{'transaction':None,'isLimit':False}},
    {'code':'AUTH_EXPIRED','msg':'expired'}])
def test_invalid_or_truncated_response_fails_closed(bad):
    with pytest.raises(ApiError): get_live_transactions(Client(bad),'demo',date=DATE)

def test_limit_saturation_fails():
    with pytest.raises(ApiError,match='INCOMPLETE'):
        get_live_transactions(Client(payload([row()])),'demo',date=DATE,limit=1)

def snapshot():
    return {'id':'demo','cash':10000,'is_limit':False,'positions':[
        {'code':'510300.XSHG','name':'示例ETF','asset_type':'基金','side':'多',
         'amount':'200股','time':DATE+' 09:05:00'}]}

def test_http_holdings_reconstruct_and_double_read(monkeypatch):
    calls=[]
    def read(*a,**k): calls.append(k);return snapshot()
    monkeypatch.setattr('jqcli.api.live_holdings.get_live_positions',read)
    monkeypatch.setattr('jqcli.api.live_holdings.read_live_page',lambda *a:pytest.fail('browser used'))
    out=get_live_holdings(Client(payload([row()])),'demo',date=DATE)
    assert len(calls)==2
    assert out['positions'][0]['quantity']==100
    assert out['reconstructed_cash']==10995
    assert out['browser_required'] is False

@pytest.mark.parametrize('changed',['positions','transactions'])
def test_changing_source_fails(monkeypatch,changed):
    n=[0]
    def read(*a,**k):
        n[0]+=1;s=snapshot()
        if changed=='positions' and n[0]==2:s['cash']=9999
        return s
    monkeypatch.setattr('jqcli.api.live_holdings.get_live_positions',read)
    class MovingClient(Client):
        def get(self,*a,**k):
            out=super().get(*a,**k)
            if changed=='transactions' and len(self.calls)==2:out['data']['transaction']=[]
            return out
    with pytest.raises(ApiError,match='SOURCE_CHANGED'):
        get_live_holdings(MovingClient(payload([row()])),'demo',date=DATE)
