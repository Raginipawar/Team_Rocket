-- MH12-DEMO-01 (the first paramedic demo login button, +919100000001) was
-- left out_of_service from earlier local testing -- real leftover state,
-- not meant to carry over into the deployed demo.
UPDATE ambulances SET status = 'available' WHERE registration_no = 'MH12-DEMO-01' AND status = 'out_of_service';
