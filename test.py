from kokoro import KPipeline
import soundfile as sf

pipeline = KPipeline(lang_code='a')

text_base = """CONSULT NOTE — CARDIOLOGY

Patient: Eleanor McPherson, 68-year-old female
Referring physician: Dr. Jonathan R. Patel
Consultant: Dr. Miriam O'Connor
Date: August 30, 2026

Reason for consultation: Evaluation of progressive exertional dyspnea and intermittent palpitations.

History: Ms. McPherson reports approximately six weeks of worsening shortness of breath when climbing stairs, associated with occasional “fluttering” sensations lasting 30–60 seconds. She denies syncope, orthopnea, paroxysmal nocturnal dyspnea, or pleuritic chest pain. ECG obtained by Dr. Patel demonstrated sinus rhythm with occasional premature atrial complexes.

Past medical history: Hypertension, type 2 diabetes mellitus, hyperlipidemia, and stage 3a chronic kidney disease.

Medications: amlodipine 5 mg PO daily; metformin XR 1,000 mg PO with supper; atorvastatin 40 mg PO nightly; empagliflozin 10 mg PO daily; ramipril 10 mg PO daily; and pantoprazole 40 mg PO PRN.

Examination: BP 138/74, HR 82, regular. No jugular venous distention. Normal S1 and S2 without murmur. Lungs clear bilaterally. No peripheral edema.

Assessment and plan: Exertional dyspnea of unclear etiology, with intermittent palpitations and multiple cardiovascular risk factors. I recommend transthoracic echocardiography, a 14-day ambulatory Zio monitor, CBC, CMP, TSH, and BNP. Continue current medications pending results. Follow up with Dr. Patel after testing is completed.
"""

text_phonetic = """Reason for consultation colon Evaluation of progressive exertional dyspnea and intermittent palpitations period

New paragraph

History colon Ms. McPherson reports approximately six weeks of worsening shortness of breath when climbing stairs comma associated with occasional quotation mark fluttering quotation mark sensations lasting 30 to 60 seconds period She denies syncope comma orthopnea comma paroxysmal nocturnal dyspnea comma or pleuritic chest pain period E C G obtained by Dr. Patel demonstrated sinus rhythm with occasional premature atrial complexes period

New paragraph

Past medical history colon Hypertension comma type 2 diabetes mellitus comma hyperlipidemia comma and stage 3a chronic kidney disease period

New paragraph

Medications colon amlodipine 5 milligrams P O daily semicolon metformin X R 1,000 milligrams P O with supper semicolon atorvastatin 40 milligrams P O nightly semicolon empagliflozin spelled E M P A G L I F L O Z I N 10 milligrams P O daily semicolon ramipril 10 milligrams P O daily semicolon and pantoprazole 40 milligrams P O P R N period

New paragraph

Examination colon B P 138 over 74 comma H R 82 comma regular period No jugular venous distention period Normal S 1 and S 2 without murmur period Lungs clear bilaterally period No peripheral edema period

New paragraph

Assessment and plan colon Exertional dyspnea of unclear etiology comma with intermittent palpitations and multiple cardiovascular risk factors period I recommend transthoracic echocardiography comma a 14-day ambulatory Zio monitor comma C B C comma C M P comma T S H comma and B N P period Continue current medications pending results period Follow up with Dr. Patel after testing is completed period
"""


generator = pipeline(text_base, voice='af_heart')

for i, (gs, ps, audio) in enumerate(generator):
    print(i, gs, ps)
    sf.write(f'{i}_base.wav', audio, 24000)

print("Audio generation complete.")

gen2 = pipeline(text_phonetic, voice='af_heart')

for i, (gs, ps, audio) in enumerate(gen2):
    print(i, gs, ps)
    sf.write(f'{i}_pho.wav', audio, 24000)

    print("Phonetics complete")
