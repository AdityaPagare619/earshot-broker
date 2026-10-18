# SLO lab report — privacy as a measurable SLO

seed=7, households=4, 30 days x 2 episodes each.
Listener: keyword fixture (LOWER BOUND on adversary strength)

## Privacy SLO: existence AUC ~= 0.5

| policy | existence AUC | triples |
|---|---|---|
| native | 0.928 | 200 |
| keyword | 0.921 | 200 |
| v1_lattice | 0.875 | 200 |
| sealed_speech | 0.497 | 200 |

## Pareto: leakage vs owner utility

| policy | leakage (AUC) | inference rate | owner utility | friction |
|---|---|---|---|---|
| native | 0.928 | 0.545 (base 0.25) | 1.000 | 0.000 |
| keyword | 0.921 | 0.273 (base 0.25) | 0.954 | 0.250 |
| v1_lattice | 0.875 | 0.273 (base 0.25) | 1.000 | 0.000 |
| sealed_speech | 0.497 | 0.273 (base 0.25) | 1.000 | 0.060 |

seed=7, households=4, listener: keyword fixture (LOWER BOUND on adversary strength)

## Counterfactual suites

Passed: 6/16

- FAIL content_swap / native: A={'voice_text': 'Rain is forecast this evening. Markets closed flat today. Team standup at ten in the morning. Prenatal checkup at Cloudnine with Dr. Mehta, 3:40 pm', 'segments': 4, 'phone_sent': False, 'mode': 'full'} B={'voice_text': 'Rain is forecast this evening. Markets closed flat today. Team standup at ten in the morning. Job interview with Zepto, Friday 11 am, third round', 'segments': 4, 'phone_sent': False, 'mode': 'full'}
- FAIL remove_item / native: A={'voice_text': 'Rain is forecast this evening. Markets closed flat today. Team standup at ten in the morning. Prenatal checkup at Cloudnine with Dr. Mehta, 3:40 pm', 'segments': 4, 'phone_sent': False, 'mode': 'full'} B={'voice_text': 'Rain is forecast this evening. Markets closed flat today. Team standup at ten in the morning.', 'segments': 3, 'phone_sent': False, 'mode': 'full'}
- FAIL remove_item / keyword: A={'voice_text': "Rain is forecast this evening. Markets closed flat today. Team standup at ten in the morning. I can't share details about that.", 'segments': 4, 'phone_sent': False, 'mode': 'cover'} B={'voice_text': 'Rain is forecast this evening. Markets closed flat today. Team standup at ten in the morning.', 'segments': 3, 'phone_sent': False, 'mode': 'full'}
- FAIL remove_item / v1_lattice: A={'voice_text': 'Rain is forecast this evening. Markets closed flat today. Team standup at ten in the morning. One private item, sent to your phone.', 'segments': 4, 'phone_sent': True, 'mode': 'cover'} B={'voice_text': 'Rain is forecast this evening. Markets closed flat today. Team standup at ten in the morning.', 'segments': 3, 'phone_sent': False, 'mode': 'full'}
- FAIL add_guest / native: A={'voice_text': "Rain is forecast this evening. Markets closed flat today. Team standup at ten in the morning. Instax camera ordered for Maya's birthday, arrives Thursday", 'segments': 4, 'phone_sent': False, 'mode': 'full'} B={'voice_text': 'Rain is forecast this evening. Markets closed flat today. Team standup at ten in the morning.', 'segments': 3, 'phone_sent': False, 'mode': 'full'}
- FAIL add_guest / keyword: A={'voice_text': "Rain is forecast this evening. Markets closed flat today. Team standup at ten in the morning. I can't share details about that.", 'segments': 4, 'phone_sent': False, 'mode': 'cover'} B={'voice_text': 'Rain is forecast this evening. Markets closed flat today. Team standup at ten in the morning.', 'segments': 3, 'phone_sent': False, 'mode': 'full'}
- FAIL add_guest / v1_lattice: A={'voice_text': 'Rain is forecast this evening. Markets closed flat today. Team standup at ten in the morning. One private item, sent to your phone.', 'segments': 4, 'phone_sent': True, 'mode': 'cover'} B={'voice_text': 'Rain is forecast this evening. Markets closed flat today. Team standup at ten in the morning.', 'segments': 3, 'phone_sent': False, 'mode': 'full'}
- FAIL replay_alone / native: A={'voice_text': 'Rain is forecast this evening. Markets closed flat today. Team standup at ten in the morning. Credit card bill overdue: Rs 18,400, pay before Friday', 'segments': 4, 'phone_sent': False, 'mode': 'full'} B={'voice_text': 'Rain is forecast this evening. Markets closed flat today. Team standup at ten in the morning.', 'segments': 3, 'phone_sent': False, 'mode': 'full'}
- FAIL replay_alone / keyword: A={'voice_text': "Rain is forecast this evening. Markets closed flat today. Team standup at ten in the morning. I can't share details about that.", 'segments': 4, 'phone_sent': False, 'mode': 'cover'} B={'voice_text': 'Rain is forecast this evening. Markets closed flat today. Team standup at ten in the morning.', 'segments': 3, 'phone_sent': False, 'mode': 'full'}
- FAIL replay_alone / v1_lattice: A={'voice_text': 'Rain is forecast this evening. Markets closed flat today. Team standup at ten in the morning. One private item, sent to your phone.', 'segments': 4, 'phone_sent': True, 'mode': 'cover'} B={'voice_text': 'Rain is forecast this evening. Markets closed flat today. Team standup at ten in the morning.', 'segments': 3, 'phone_sent': False, 'mode': 'full'}

## What this does NOT prove

- The fixture listener is a LOWER BOUND on adversary strength; a smarter adversary could do better.
- Policy-layer results are not server evidence; the wire layer is the existing trace-harness.
- Synthetic households are not real households; belief noise is a fixture model.
- No timing-channel claim: timing-shape is a structural proxy (segments, phone_sent), measured for real at the wire layer.
