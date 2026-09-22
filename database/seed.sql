-- Dados fictícios para demonstração. Contas são criadas com senha derivada pelo inicializador.
INSERT INTO sectors(id,name) VALUES(1,'Administrativo'),(2,'Operações'),(3,'Almoxarifado');
INSERT INTO partners(id,name,contact) VALUES(1,'Cooperativa Exemplo','Contato fictício para demonstração'),(2,'Destinação Exemplo','Contato fictício para demonstração');
INSERT INTO records(metric,date,quantity,sector_id,partner_id,waste_type,destination,note,created_by) VALUES
('agua','2026-08-15',42,1,NULL,'','','Consumo do período de agosto',2),
('agua','2026-09-15',35,1,NULL,'','','Consumo do período de setembro',2),
('agua','2026-09-15',110,2,NULL,'','','Consumo de operações',2),
('energia','2026-08-15',1650,1,NULL,'','','Energia de agosto',2),
('energia','2026-09-15',1430,1,NULL,'','','Energia de setembro',2),
('energia','2026-09-15',2850,2,NULL,'','','Energia de operações',2),
('residuos','2026-09-10',120,2,1,'Papel e papelão','Reciclagem','Coleta de exemplo',2),
('residuos','2026-09-12',35,3,2,'Rejeitos','Destinação final','Coleta de exemplo',2),
('residuos','2026-09-18',80,2,1,'Plástico','Reciclagem','Coleta de exemplo',2);
INSERT INTO goals(title,metric,sector_id,start_date,end_date,limit_value) VALUES
('Limite de água no administrativo','agua',1,'2026-09-01','2026-09-30',38),
('Limite de energia nas operações','energia',2,'2026-09-01','2026-09-30',2600),
('Limite de resíduos nas operações','residuos',2,'2026-09-01','2026-09-30',250);
INSERT INTO actions(title,description,sector_id,owner_id,due_date,status,evidence,completed_at) VALUES
('Inspecionar pontos de consumo','Verificar equipamentos ligados fora do expediente e registrar medidas.',2,2,'2026-09-30','em_andamento','',NULL),
('Revisar segregação de resíduos','Conferir identificação dos recipientes e orientação dos responsáveis.',3,1,'2026-10-05','aberta','',NULL);
