-- Demo hospital had only 2 rooms total (both already occupied/reserved) and
-- 0 available ventilators -- every hospital-request ran out of room/resource
-- after 1-2 test SOS calls and silently fell through to "no_hospital"
-- escalation. Bumping to a healthy demo-sized pool across every room type
-- and resource type.
INSERT INTO rooms (hospital_id, code, type, status)
SELECT 'a61d76bf-457c-47c0-bee7-134134835119', t.code, t.type, 'free'
FROM (VALUES
  ('ER-01','er_bed'),('ER-02','er_bed'),('ER-03','er_bed'),('ER-04','er_bed'),('ER-05','er_bed'),
  ('ER-06','er_bed'),('ER-07','er_bed'),('ER-08','er_bed'),('ER-09','er_bed'),('ER-10','er_bed'),
  ('RB-01','resus_bay'),('RB-02','resus_bay'),('RB-03','resus_bay'),('RB-04','resus_bay'),
  ('TB-01','trauma_bay'),('TB-02','trauma_bay'),('TB-03','trauma_bay'),
  ('ICU-01','icu_bed'),('ICU-02','icu_bed'),('ICU-03','icu_bed'),('ICU-04','icu_bed'),('ICU-05','icu_bed'),
  ('LR-01','labour_room'),('LR-02','labour_room'),
  ('BU-01','burns_unit'),('BU-02','burns_unit'),
  ('PE-01','pediatric_er'),('PE-02','pediatric_er'),('PE-03','pediatric_er')
) AS t(code, type)
ON CONFLICT (hospital_id, code) DO NOTHING;

INSERT INTO hospital_resources (hospital_id, type, total, available, reserved, reported_at)
SELECT 'a61d76bf-457c-47c0-bee7-134134835119', t.type, 20, 20, 0, now()
FROM (VALUES
  ('ventilator'),('cath_lab'),('ct_scanner'),('mri'),('defibrillator'),
  ('blood_o_neg'),('blood_o_pos'),('blood_a_pos'),('blood_b_pos'),('blood_ab_pos'),
  ('dialysis'),('operating_theatre')
) AS t(type)
ON CONFLICT (hospital_id, type) DO UPDATE SET total=20, available=20, reserved=0, reported_at=now();
