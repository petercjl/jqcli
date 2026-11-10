import json
from click.testing import CliRunner
from jqcli.cli import main


def test_holdings_name_cli(monkeypatch,tmp_path):
    monkeypatch.setattr('jqcli.commands.live.make_client',lambda app:object())
    monkeypatch.setattr('jqcli.commands.live.list_live_trades',lambda *a,**k:{'items':[{'id':'demo','name':'示例模拟盘'}]})
    def query(client,live_id,**kw):
        assert live_id=='demo' and kw['date']=='2026-01-06'
        return {'positions':[],'reconstructed_cash':100,'cash':None}
    monkeypatch.setattr('jqcli.api.live_holdings.get_live_holdings',query)
    r=CliRunner().invoke(main,['--config',str(tmp_path/'config.json'),'--token','test','--format','json','live','holdings','--name','示例模拟盘','--date','2026-01-06'])
    assert r.exit_code==0,r.output
    assert json.loads(r.output)['cash'] is None
