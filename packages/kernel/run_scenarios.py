"""Finite synthetic trace: no claims about real sensing or audio."""
import json
from dataclasses import replace
from kernel import Context, Fact, Kernel, Label

k=Kernel()
private=Fact('appt', 'Prenatal visit at 15:40', Label(frozenset({'priya'}), frozenset({'health'})))
public=Fact('groceries', 'Collect groceries after 6.', Label(frozenset({'*'})))
ctx=Context('demo-house','priya',frozenset({'priya'}),1,100,True,True,True,7)
lease=k.prepare(private,ctx,100)
changed=replace(ctx,audience=frozenset({'priya','mom'}),epoch=2)
receipt=k.accept('demo-house','priya','synthetic-request',(private,public),100)
trace={
 'fixture_notice':'Synthetic; groceries time is independently public, not derived from the private event.',
 'public_projection_alone_uncontrolled_host':k.room_projection((public,private),replace(ctx,controlled_renderer=False),100),
 'public_projection_after_entry_uncontrolled_host':k.room_projection((public,private),replace(changed,controlled_renderer=False),100.1),
 'controlled_host_pending_lease_denied_after_entry':k.redeem(lease,changed,100.1) is None,
 'request_receipt_public':receipt,
 'owner_private_contents':[f.value for f in k.open_private(receipt['receipt'],'demo-house','priya',True,101)]
}
try:
 k.open_private(receipt['receipt'],'demo-house','mom',True,101)
 trace['other_person_denied']=False
except PermissionError:
 trace['other_person_denied']=True
print(json.dumps(trace,indent=2))
