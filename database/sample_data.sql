-- database/sample_data.sql
USE hoopwatch;

-- USERS (include 1 admin + test users)
INSERT INTO users (email, password_hash, role) VALUES
('admin@hoopwatch.com', NULL, 'admin'),
('base1@hoopwatch.com', NULL, 'base'),
('pro1@hoopwatch.com', NULL, 'pro'),
('base2@hoopwatch.com', NULL, 'base'),
('base3@hoopwatch.com', NULL, 'base');

-- TEAMS (30 sample NBA teams)
<<<<<<< HEAD
INSERT INTO teams (nba_team_id, name, abbreviation, conference, logo_url, city, state, country, arena_name) VALUES
('1610612737','Atlanta Hawks','ATL','East','/static/Logos/Atlanta_Hawks.png','Atlanta','GA','USA','State Farm Arena'),
('1610612738','Boston Celtics','BOS','East','/static/Logos/Boston_Celtics.png','Boston','MA','USA','TD Garden'),
('1610612751','Brooklyn Nets','BKN','East','/static/Logos/Brooklyn_Nets.png','Brooklyn','NY','USA','Barclays Center'),
('1610612766','Charlotte Hornets','CHA','East','/static/Logos/Charlotte__Hornets.png','Charlotte','NC','USA','Spectrum Center'),
('1610612741','Chicago Bulls','CHI','East','/static/Logos/Chicago_Bulls.png','Chicago','IL','USA','United Center'),
('1610612739','Cleveland Cavaliers','CLE','East','/static/Logos/Cleveland_Cavaliers.png','Cleveland','OH','USA','Rocket Mortgage FieldHouse'),
('1610612742','Dallas Mavericks','DAL','West','/static/Logos/Dallas_Mavericks.png','Dallas','TX','USA','American Airlines Center'),
('1610612743','Denver Nuggets','DEN','West','/static/Logos/Denver_Nuggets.png','Denver','CO','USA','Ball Arena'),
('1610612765','Detroit Pistons','DET','East','/static/Logos/Detroit_Pistons.png','Detroit','MI','USA','Little Caesars Arena'),
('1610612744','Golden State Warriors','GSW','West','/static/Logos/Golden_State_Warriors.png','San Francisco','CA','USA','Chase Center'),
('1610612745','Houston Rockets','HOU','West','/static/Logos/Houston_Rockets.png','Houston','TX','USA','Toyota Center'),
('1610612754','Indiana Pacers','IND','East','/static/Logos/Indiana_Pacers.png','Indianapolis','IN','USA','Gainbridge Fieldhouse'),
('1610612746','Los Angeles Clippers','LAC','West','/static/Logos/Los_Angeles_Clippers.png','Los Angeles','CA','USA','Intuit Dome'),
('1610612747','Los Angeles Lakers','LAL','West','/static/Logos/Los_Angeles_Lakers.png','Los Angeles','CA','USA','Crypto.com Arena'),
('1610612763','Memphis Grizzlies','MEM','West','/static/Logos/Memphis_Grizzlies.png','Memphis','TN','USA','FedExForum'),
('1610612748','Miami Heat','MIA','East','/static/Logos/Miami_Heat.png','Miami','FL','USA','Kaseya Center'),
('1610612749','Milwaukee Bucks','MIL','East','/static/Logos/Milwaukee_Bucks.png','Milwaukee','WI','USA','Fiserv Forum'),
('1610612750','Minnesota Timberwolves','MIN','West','/static/Logos/Minnesota_Timberwolves.png','Minneapolis','MN','USA','Target Center'),
('1610612740','New Orleans Pelicans','NOP','West','/static/Logos/New_Orleans_Pelicans.png','New Orleans','LA','USA','Smoothie King Center'),
('1610612752','New York Knicks','NYK','East','/static/Logos/New_York_Knicks.png','New York','NY','USA','Madison Square Garden'),
('1610612760','Oklahoma City Thunder','OKC','West','/static/Logos/OKC-Thunder.png','Oklahoma City','OK','USA','Paycom Center'),
('1610612753','Orlando Magic','ORL','East','/static/Logos/Orlando_Magic.png','Orlando','FL','USA','Kia Center'),
('1610612755','Philadelphia 76ers','PHI','East','/static/Logos/Philadelphia_76ers.png','Philadelphia','PA','USA','Wells Fargo Center'),
('1610612756','Phoenix Suns','PHX','West','/static/Logos/Phoenix_Suns.png','Phoenix','AZ','USA','Footprint Center'),
('1610612757','Portland Trail Blazers','POR','West','/static/Logos/Portland_Trail_Blazers.png','Portland','OR','USA','Moda Center'),
('1610612758','Sacramento Kings','SAC','West','/static/Logos/Sacramento_Kings.png','Sacramento','CA','USA','Golden 1 Center'),
('1610612759','San Antonio Spurs','SAS','West','/static/Logos/San_Antonio_Spurs.png','San Antonio','TX','USA','Frost Bank Center'),
('1610612761','Toronto Raptors','TOR','East','/static/Logos/Toronto_Raptors.png','Toronto','ON','Canada','Scotiabank Arena'),
('1610612762','Utah Jazz','UTA','West','/static/Logos/Utah_Jazz.png','Salt Lake City','UT','USA','Delta Center'),
('1610612764','Washington Wizards','WAS','East','/static/Logos/Washington_Wizards.png','Washington','DC','USA','Capital One Arena');
=======
INSERT INTO teams (nba_team_id, name, abbreviation, conference, logo_url) VALUES
('1610612737','Atlanta Hawks','ATL','East','/static/Logos/Atlanta_Hawks.png'),
('1610612738','Boston Celtics','BOS','East','/static/Logos/Boston_Celtics.png'),
('1610612751','Brooklyn Nets','BKN','East','/static/Logos/Brooklyn_Nets.png'),
('1610612766','Charlotte Hornets','CHA','East','/static/Logos/Charlotte__Hornets.png'),
('1610612741','Chicago Bulls','CHI','East','/static/Logos/Chicago_Bulls.png'),
('1610612739','Cleveland Cavaliers','CLE','East','/static/Logos/Cleveland_Cavaliers.png'),
('1610612742','Dallas Mavericks','DAL','West','/static/Logos/Dallas_Mavericks.png'),
('1610612743','Denver Nuggets','DEN','West','/static/Logos/Denver_Nuggets.png'),
('1610612765','Detroit Pistons','DET','East','/static/Logos/Detroit_Pistons.png'),
('1610612744','Golden State Warriors','GSW','West','/static/Logos/Golden_State_Warriors.png'),
('1610612745','Houston Rockets','HOU','West','/static/Logos/Houston_Rockets.png'),
('1610612754','Indiana Pacers','IND','East','/static/Logos/Indiana_Pacers.png'),
('1610612746','Los Angeles Clippers','LAC','West','/static/Logos/Los_Angeles_Clippers.png'),
('1610612747','Los Angeles Lakers','LAL','West','/static/Logos/Los_Angeles_Lakers.png'),
('1610612763','Memphis Grizzlies','MEM','West','/static/Logos/Memphis_Grizzlies.png'),
('1610612748','Miami Heat','MIA','East','/static/Logos/Miami_Heat.png'),
('1610612749','Milwaukee Bucks','MIL','East','/static/Logos/Milwaukee_Bucks.png'),
('1610612750','Minnesota Timberwolves','MIN','West','/static/Logos/Minnesota_Timberwolves.png'),
('1610612740','New Orleans Pelicans','NOP','West','/static/Logos/New_Orleans_Pelicans.png'),
('1610612752','New York Knicks','NYK','East','/static/Logos/New_York_Knicks.png'),
('1610612760','Oklahoma City Thunder','OKC','West','/static/Logos/OKC-Thunder.png'),
('1610612753','Orlando Magic','ORL','East','/static/Logos/Orlando_Magic.png'),
('1610612755','Philadelphia 76ers','PHI','East','/static/Logos/Philadelphia_76ers.png'),
('1610612756','Phoenix Suns','PHX','West','/static/Logos/Phoenix_Suns.png'),
('1610612757','Portland Trail Blazers','POR','West','/static/Logos/Portland_Trail_Blazers.png'),
('1610612758','Sacramento Kings','SAC','West','/static/Logos/Sacramento_Kings.png'),
('1610612759','San Antonio Spurs','SAS','West','/static/Logos/San_Antonio_Spurs.png'),
('1610612761','Toronto Raptors','TOR','East','/static/Logos/Toronto_Raptors.png'),
('1610612762','Utah Jazz','UTA','West','/static/Logos/Utah_Jazz.png'),
('1610612764','Washington Wizards','WAS','East','/static/Logos/Washington_Wizards.png');
-- TEAM LOCATIONS
INSERT INTO team_locations (team_id, city, state, country, arena_name) VALUES
((SELECT team_id FROM teams WHERE nba_team_id='1610612737'),'Atlanta','GA','USA','State Farm Arena'),
((SELECT team_id FROM teams WHERE nba_team_id='1610612738'),'Boston','MA','USA','TD Garden'),
((SELECT team_id FROM teams WHERE nba_team_id='1610612751'),'Brooklyn','NY','USA','Barclays Center'),
((SELECT team_id FROM teams WHERE nba_team_id='1610612766'),'Charlotte','NC','USA','Spectrum Center'),
((SELECT team_id FROM teams WHERE nba_team_id='1610612741'),'Chicago','IL','USA','United Center'),
((SELECT team_id FROM teams WHERE nba_team_id='1610612739'),'Cleveland','OH','USA','Rocket Mortgage FieldHouse'),
((SELECT team_id FROM teams WHERE nba_team_id='1610612742'),'Dallas','TX','USA','American Airlines Center'),
((SELECT team_id FROM teams WHERE nba_team_id='1610612743'),'Denver','CO','USA','Ball Arena'),
((SELECT team_id FROM teams WHERE nba_team_id='1610612765'),'Detroit','MI','USA','Little Caesars Arena'),
((SELECT team_id FROM teams WHERE nba_team_id='1610612744'),'San Francisco','CA','USA','Chase Center'),
((SELECT team_id FROM teams WHERE nba_team_id='1610612745'),'Houston','TX','USA','Toyota Center'),
((SELECT team_id FROM teams WHERE nba_team_id='1610612754'),'Indianapolis','IN','USA','Gainbridge Fieldhouse'),
((SELECT team_id FROM teams WHERE nba_team_id='1610612746'),'Los Angeles','CA','USA','Intuit Dome'),
((SELECT team_id FROM teams WHERE nba_team_id='1610612747'),'Los Angeles','CA','USA','Crypto.com Arena'),
((SELECT team_id FROM teams WHERE nba_team_id='1610612763'),'Memphis','TN','USA','FedExForum'),
((SELECT team_id FROM teams WHERE nba_team_id='1610612748'),'Miami','FL','USA','Kaseya Center'),
((SELECT team_id FROM teams WHERE nba_team_id='1610612749'),'Milwaukee','WI','USA','Fiserv Forum'),
((SELECT team_id FROM teams WHERE nba_team_id='1610612750'),'Minneapolis','MN','USA','Target Center'),
((SELECT team_id FROM teams WHERE nba_team_id='1610612740'),'New Orleans','LA','USA','Smoothie King Center'),
((SELECT team_id FROM teams WHERE nba_team_id='1610612752'),'New York','NY','USA','Madison Square Garden'),
((SELECT team_id FROM teams WHERE nba_team_id='1610612760'),'Oklahoma City','OK','USA','Paycom Center'),
((SELECT team_id FROM teams WHERE nba_team_id='1610612753'),'Orlando','FL','USA','Kia Center'),
((SELECT team_id FROM teams WHERE nba_team_id='1610612755'),'Philadelphia','PA','USA','Wells Fargo Center'),
((SELECT team_id FROM teams WHERE nba_team_id='1610612756'),'Phoenix','AZ','USA','Footprint Center'),
((SELECT team_id FROM teams WHERE nba_team_id='1610612757'),'Portland','OR','USA','Moda Center'),
((SELECT team_id FROM teams WHERE nba_team_id='1610612758'),'Sacramento','CA','USA','Golden 1 Center'),
((SELECT team_id FROM teams WHERE nba_team_id='1610612759'),'San Antonio','TX','USA','Frost Bank Center'),
((SELECT team_id FROM teams WHERE nba_team_id='1610612761'),'Toronto','ON','Canada','Scotiabank Arena'),
((SELECT team_id FROM teams WHERE nba_team_id='1610612762'),'Salt Lake City','UT','USA','Delta Center'),
((SELECT team_id FROM teams WHERE nba_team_id='1610612764'),'Washington','DC','USA','Capital One Arena');
>>>>>>> main
-- STANDINGS (sample)
INSERT INTO team_standings (team_id, wins, losses) VALUES
(1, 28, 25),
(2, 41, 12),
(3, 25, 28),
(4, 22, 31),
(5, 24, 29),
(6, 33, 20),
(7, 31, 22),
(8, 35, 18),
(9, 18, 35),
(10, 30, 23),
(11, 29, 24),
(12, 27, 26),
(13, 32, 21),
(14, 32, 21),
(15, 26, 27),
(16, 28, 25),
(17, 34, 19),
(18, 36, 17),
(19, 23, 30),
(20, 30, 23),
(21, 35, 18),
(22, 17, 36),
(23, 31, 22),
(24, 29, 24),
(25, 19, 34),
(26, 28, 25),
(27, 18, 35),
(28, 20, 33),
(29, 21, 32),
(30, 16, 37);

-- PLAYERS (30 sample, 3 per some teams)
INSERT INTO players (nba_player_id, team_id, first_name, last_name, position, jersey_number, height_in, weight_lb, birth_date, headshot_url) VALUES
-- ATL (1)
('p_atl_1',1,'Trae','Young','PG',11,73,164,'1998-09-19',NULL),
('p_atl_2',1,'Dejounte','Murray','SG',5,77,180,'1996-09-19',NULL),
('p_atl_3',1,'Clint','Capela','C',15,82,240,'1994-05-18',NULL),

-- BOS (2)
('p_bos_1',2,'Jayson','Tatum','SF',0,80,210,'1998-03-03',NULL),
('p_bos_2',2,'Jaylen','Brown','SG',7,78,223,'1996-10-24',NULL),
('p_bos_3',2,'Derrick','White','PG',4,76,205,'1990-06-12',NULL),

-- BKN (3)
('p_bkn_1',3,'Mikal','Bridges','SF',1,78,209,'1996-08-30',NULL),
('p_bkn_2',3,'Ben','Simmons','PG',10,83,240,'1996-07-20',NULL),
('p_bkn_3',3,'Cam','Thomas','SG',24,75,210,'2001-10-13',NULL),

-- CHA (4)
('p_cha_1',4,'LaMelo','Ball','PG',1,79,190,'2001-08-22',NULL),
('p_cha_2',4,'Miles','Bridges','SF',0,79,225,'1998-03-21',NULL),
('p_cha_3',4,'Brandon','Miller','SF',24,81,200,'2002-11-22',NULL),

-- CHI (5)
('p_chi_1',5,'Zach','LaVine','SG',8,77,200,'1995-03-10',NULL),
('p_chi_2',5,'DeMar','DeRozan','SF',11,78,220,'1989-08-07',NULL),
('p_chi_3',5,'Nikola','Vucevic','C',9,82,260,'1990-10-24',NULL),

-- CLE (6)
('p_cle_1',6,'Donovan','Mitchell','SG',45,75,215,'1996-09-07',NULL),
('p_cle_2',6,'Darius','Garland','PG',10,73,192,'2000-01-26',NULL),
('p_cle_3',6,'Evan','Mobley','PF',4,83,215,'2001-06-18',NULL),

-- DAL (7)
('p_dal_1',7,'Luka','Doncic','PG',77,79,230,'1999-02-28',NULL),
('p_dal_2',7,'Kyrie','Irving','PG',11,74,195,'1992-03-23',NULL),
('p_dal_3',7,'Tim','Hardaway Jr.','SG',11,77,205,'1992-03-16',NULL),

-- DEN (8)
('p_den_1',8,'Nikola','Jokic','C',15,83,284,'1995-02-19',NULL),
('p_den_2',8,'Jamal','Murray','PG',27,76,215,'1997-02-23',NULL),
('p_den_3',8,'Michael','Porter Jr.','SF',1,82,218,'1998-06-29',NULL),

-- DET (9)
('p_det_1',9,'Cade','Cunningham','PG',2,78,220,'2001-09-25',NULL),
('p_det_2',9,'Jaden','Ivey','SG',23,76,200,'2002-02-13',NULL),
('p_det_3',9,'Jalen','Duren','C',0,82,250,'2003-11-18',NULL),

-- GSW (10)
('p_gsw_1',10,'Stephen','Curry','PG',30,74,185,'1988-03-14',NULL),
('p_gsw_2',10,'Klay','Thompson','SG',11,78,215,'1990-02-08',NULL),
('p_gsw_3',10,'Draymond','Green','PF',23,78,230,'1990-03-04',NULL),

-- HOU (11)
('p_hou_1',11,'Jalen','Green','SG',4,76,186,'2002-02-09',NULL),
('p_hou_2',11,'Alperen','Sengun','C',28,82,240,'2002-07-25',NULL),
('p_hou_3',11,'Fred','VanVleet','PG',5,73,197,'1994-02-25',NULL),

-- IND (12)
('p_ind_1',12,'Tyrese','Haliburton','PG',0,77,185,'2000-02-29',NULL),
('p_ind_2',12,'Myles','Turner','C',33,83,250,'1996-03-24',NULL),
('p_ind_3',12,'Bennedict','Mathurin','SG',00,77,210,'2002-06-19',NULL),

-- LAC (13)
('p_lac_1',13,'Kawhi','Leonard','SF',2,79,225,'1991-06-29',NULL),
('p_lac_2',13,'Paul','George','SG',13,80,220,'1990-05-02',NULL),
('p_lac_3',13,'James','Harden','PG',1,77,220,'1989-08-26',NULL),

-- LAL (14)
('p_lal_1',14,'LeBron','James','SF',23,81,250,'1984-12-30',NULL),
('p_lal_2',14,'Anthony','Davis','PF',3,82,253,'1993-03-11',NULL),
('p_lal_3',14,'Austin','Reaves','SG',15,77,197,'1998-05-29',NULL),

-- MEM (15)
('p_mem_1',15,'Ja','Morant','PG',12,75,174,'1999-08-10',NULL),
('p_mem_2',15,'Jaren','Jackson Jr.','PF',13,82,242,'1999-09-15',NULL),
('p_mem_3',15,'Desmond','Bane','SG',22,77,215,'1998-06-25',NULL),

-- MIA (16)
('p_mia_1',16,'Jimmy','Butler','SF',22,79,230,'1989-09-14',NULL),
('p_mia_2',16,'Bam','Adebayo','C',13,81,255,'1997-07-18',NULL),
('p_mia_3',16,'Tyler','Herro','SG',14,77,195,'2000-01-20',NULL),

-- MIL (17)
('p_mil_1',17,'Giannis','Antetokounmpo','PF',34,83,242,'1994-12-06',NULL),
('p_mil_2',17,'Damian','Lillard','PG',0,74,195,'1990-07-15',NULL),
('p_mil_3',17,'Khris','Middleton','SF',22,79,222,'1991-08-12',NULL),

-- MIN (18)
('p_min_1',18,'Anthony','Edwards','SG',5,76,225,'2001-08-05',NULL),
('p_min_2',18,'Karl-Anthony','Towns','C',32,84,248,'1995-11-15',NULL),
('p_min_3',18,'Rudy','Gobert','C',27,85,258,'1992-06-26',NULL),

-- NOP (19)
('p_nop_1',19,'Zion','Williamson','PF',1,78,284,'2000-07-06',NULL),
('p_nop_2',19,'Brandon','Ingram','SF',14,80,190,'1997-09-02',NULL),
('p_nop_3',19,'CJ','McCollum','SG',3,75,190,'1991-09-19',NULL),

-- NYK (20)
('p_nyk_1',20,'Jalen','Brunson','PG',11,74,190,'1996-08-31',NULL),
('p_nyk_2',20,'Julius','Randle','PF',30,80,250,'1994-11-29',NULL),
('p_nyk_3',20,'OG','Anunoby','SF',8,79,240,'1997-07-17',NULL),

-- OKC (21)
('p_okc_1',21,'Shai','Gilgeous-Alexander','PG',2,78,195,'1998-07-12',NULL),
('p_okc_2',21,'Chet','Holmgren','C',7,85,208,'2002-05-01',NULL),
('p_okc_3',21,'Jalen','Williams','SF',8,78,211,'2001-04-14',NULL),

-- ORL (22)
('p_orl_1',22,'Paolo','Banchero','PF',5,82,250,'2002-11-12',NULL),
('p_orl_2',22,'Franz','Wagner','SF',22,81,220,'2001-08-27',NULL),
('p_orl_3',22,'Jalen','Suggs','SG',4,76,205,'2001-06-03',NULL),

-- PHI (23)
('p_phi_1',23,'Joel','Embiid','C',21,84,280,'1994-03-16',NULL),
('p_phi_2',23,'Tyrese','Maxey','PG',0,74,200,'2000-11-04',NULL),
('p_phi_3',23,'Tobias','Harris','PF',12,80,226,'1992-07-15',NULL),

-- PHX (24)
('p_phx_1',24,'Kevin','Durant','SF',35,82,240,'1988-09-29',NULL),
('p_phx_2',24,'Devin','Booker','SG',1,78,206,'1996-10-30',NULL),
('p_phx_3',24,'Bradley','Beal','SG',3,75,207,'1993-06-28',NULL),

-- POR (25)
('p_por_1',25,'Anfernee','Simons','SG',1,75,193,'1999-06-08',NULL),
('p_por_2',25,'Scoot','Henderson','PG',00,75,202,'2004-02-03',NULL),
('p_por_3',25,'Jerami','Grant','SF',9,80,210,'1994-03-12',NULL),

-- SAC (26)
('p_sac_1',26,'De''Aaron','Fox','PG',5,75,185,'1997-12-20',NULL),
('p_sac_2',26,'Domantas','Sabonis','C',10,83,240,'1996-05-03',NULL),
('p_sac_3',26,'Keegan','Murray','SF',13,80,225,'2000-08-19',NULL),

-- SAS (27)
('p_sas_1',27,'Victor','Wembanyama','C',1,87,210,'2004-01-04',NULL),
('p_sas_2',27,'Devin','Vassell','SG',24,77,200,'2000-08-23',NULL),
('p_sas_3',27,'Keldon','Johnson','SF',3,77,220,'1999-10-11',NULL),

-- TOR (28)
('p_tor_1',28,'Scottie','Barnes','SF',4,79,237,'2001-08-01',NULL),
('p_tor_2',28,'RJ','Barrett','SG',9,78,214,'2000-06-14',NULL),
('p_tor_3',28,'Jakob','Poeltl','C',19,85,245,'1995-10-15',NULL),

-- UTA (29)
('p_uta_1',29,'Lauri','Markkanen','PF',23,84,240,'1997-05-22',NULL),
('p_uta_2',29,'Jordan','Clarkson','SG',00,76,194,'1992-06-07',NULL),
('p_uta_3',29,'Collin','Sexton','PG',2,73,190,'1999-01-04',NULL),

-- WAS (30)
('p_was_1',30,'Kyle','Kuzma','PF',33,81,221,'1995-07-24',NULL),
('p_was_2',30,'Jordan','Poole','SG',13,76,194,'1999-06-19',NULL),
('p_was_3',30,'Tyus','Jones','PG',5,72,196,'1996-05-10',NULL);
-- GAMES (sample around PR2 date)
INSERT INTO games (nba_game_id, home_team_id, away_team_id, game_date, start_time, status) VALUES
('g_1001', 1, 2, '2026-02-14', '19:30:00', 'scheduled'),
('g_1002', 3, 4, '2026-02-14', '20:00:00', 'scheduled'),
('g_1003', 5, 6, '2026-02-15', '18:00:00', 'scheduled'),
('g_1004', 7, 8, '2026-02-15', '20:30:00', 'scheduled'),
('g_1005', 9, 10,'2026-02-16', '19:00:00', 'scheduled');

-- GAME CACHE (optional demo)
INSERT INTO game_cache (game_id, home_score, away_score, period, clock, expires_at) VALUES
(1, 0, 0, NULL, NULL, DATE_ADD(NOW(), INTERVAL 2 MINUTE)),
(2, 0, 0, NULL, NULL, DATE_ADD(NOW(), INTERVAL 2 MINUTE));

-- DAILY CONTENT (Fact of the Day)
INSERT INTO daily_content (content_date, fact_text, featured_game_id, admin_user_id) VALUES
('2026-02-14','Today’s featured matchup: BOS vs LAL. Watch for big runs in the 3rd quarter.', 1, 1),
('2026-02-13','Teams that protect the paint usually win the free throw battle.', NULL, 1),
('2026-02-12','A strong bench unit can flip momentum without changing the game plan.', NULL, 1);

-- TEAMS TO WATCH
INSERT INTO teams_to_watch (watch_date, team_id, admin_user_id) VALUES
('2026-02-14', 2, 1),
('2026-02-14', 14, 1),
('2026-02-14', 21, 1);

-- FAVORITES (demo)
INSERT INTO favorites (user_id, team_id) VALUES
(2, 9),
(2, 2),
(3, 21);
