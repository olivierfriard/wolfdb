regions = [
		{
			"nome": "Abruzzo",
			"capoluoghi": ["Chieti", "L'Aquila", "Pescara", "Teramo"],
			"province":["CH","AQ","PE","TE"]
		},
		{
			"nome": "Basilicata",
			"capoluoghi": ["Matera", "Potenza"],
			"province":["MT","PZ"]
		},
		{
			"nome": "Calabria",
			"capoluoghi": ["Catanzaro", "Cosenza", "Crotone", "Reggio Calabria", "Vibo Valentia"],
			"province":["CZ","CS","KR","RC","VV"]
		},
		{
			"nome": "Campania",
			"capoluoghi": ["Avellino", "Benevento", "Caserta", "Napoli", "Salerno"],
			"province":["AV","BN","CE","NA","SA"]
		},
		{
			"nome": "Emilia-Romagna",
			"capoluoghi": ["Bologna", "Ferrara", "Forlì-Cesena", "Modena", "Parma", "Piacenza", "Ravenna", "Reggio Emilia", "Rimini"],
			"province":["BO","FE","FC","MO","PR","PC","RA","RE","RN"]
		},
		{
			"nome": "Friuli-Venezia Giulia",
			"capoluoghi": ["Gorizia", "Pordenone", "Trieste", "Udine"],
			"province":["GO","PN","TS","UD"]
		},
		{
			"nome": "Lazio",
			"capoluoghi": ["Frosinone", "Latina", "Rieti", "Roma", "Viterbo"],
			"province":["FR","LT","RI","RM","VT"]
		},
		{
			"nome": "Liguria",
			"capoluoghi": ["Genova", "Imperia", "La Spezia", "Savona"],
			"province":["GE","IM","SP","SV"]
		},
		{
			"nome": "Lombardia",
			"capoluoghi": ["Bergamo", "Brescia", "Como", "Cremona", "Lecco", "Lodi", "Mantova", "Milano", "Monza e Brianza", "Pavia", "Sondrio", "Varese"],
			"province":["BG","BS","CO","CR","LC","LO","MN","MI","MB","PV","SO","VA"]
		},
		{
			"nome": "Marche",
			"capoluoghi": ["Ancona", "Ascoli Piceno", "Fermo", "Macerata", "Pesaro e Urbino"],
			"province":["AN","AP","FM","MC","PU"]
		},
		{
			"nome": "Molise",
			"capoluoghi": ["Campobasso", "Isernia"],
			"province":["CB","IS"]
		},
		{
			"nome": "Piemonte",
			"capoluoghi": ["Alessandria", "Asti", "Biella", "Cuneo", "Novara", "Torino", "Verbano Cusio Ossola", "Vercelli"],
			"province":["AL","AT","BI","CN","NO","TO","VB","VC"]
		},
		{
			"nome": "Puglia",
			"capoluoghi": ["Bari", "Barletta-Andria-Trani", "Brindisi", "Lecce", "Foggia", "Taranto"],
			"province":["BA","BT","BR","LE","FG","TA"]
		},
		{
			"nome": "Sardegna",
			"capoluoghi": ["Cagliari", "Carbonia-Iglesias", "Medio Campidano", "Nuoro", "Ogliastra", "Olbia-Tempio", "Oristano", "Sassari"],
			"province":["CA","CI","VS","NU","OG","OT","OR","SS"]
		},
		{
			"nome": "Sicilia",
			"capoluoghi": ["Agrigento", "Caltanissetta", "Catania", "Enna", "Messina", "Palermo", "Ragusa", "Siracusa", "Trapani"],
			"province":["AG","CL","CT","EN","ME","PA","RG","SR","TP"]
		},
		{
			"nome": "Toscana",
			"capoluoghi": ["Arezzo", "Firenze", "Grosseto", "Livorno", "Lucca", "Massa e Carrara", "Pisa", "Pistoia", "Prato", "Siena"],
			"province":["AR","FI","GR","LI","LU","MS","PI","PT","PO","SI"]
		},
		{
			"nome": "Trentino-Alto Adige",
			"capoluoghi": ["Bolzano", "Trento"],
			"province":["BZ","TN"]
		},
		{
			"nome": "Umbria",
			"capoluoghi": ["Perugia", "Terni"],
			"province":["PG","TR"]
		},
		{
			"nome": "Valle d'Aosta",
			"capoluoghi": ["Aosta"],
			"province":["AO"]
		},
		{
			"nome": "Veneto",
			"capoluoghi": ["Belluno", "Padova", "Rovigo", "Treviso", "Venezia", "Verona", "Vicenza"],
			"province":["BL","PD","RO","TV","VE","VR","VI"]
		}
	]


province_codes = {
	"AG": {"nome": "Agrigento", "regione": "Sicilia"},
	"AL": {"nome": "Alessandria", "regione": "Piemonte"},
	"AN": {"nome": "Ancona", "regione": "Marche"},
	"AO": {"nome": "Aosta", "regione": "Valle d'Aosta"},
	"AQ": {"nome": "L'Aquila", "regione": "Abruzzo"},
	"AR": {"nome": "Arezzo", "regione": "Toscana"},
	"AP": {"nome": "Ascoli", "regione": "iceno 	Marche"},
	"AT": {"nome": "Asti", "regione": "Piemonte"},
	"AV": {"nome": "Avellino", "regione": "Campania"},
	"BA": {"nome": "Bari", "regione": "Puglia"},
	"BT": {"nome": "Barletta-Andria-Trani", "regione": "Puglia"},
	"BL": {"nome": "Belluno", "regione": "Veneto"},
	"BN": {"nome": "Benevento", "regione": "Campania"},
	"BG": {"nome": "Bergamo", "regione": "Lombardia"},
	"BI": {"nome": "Biella", "regione": "Piemonte"},
	"BO": {"nome": "Bologna", "regione": "Emilia Romagna"},
	"BZ": {"nome": "Bolzano", "regione": "Trentino Alto Adige"},
	"BS": {"nome": "Brescia", "regione": "Lombardia"},
	"BR": {"nome": "Brindisi", "regione": "Puglia"},
	"CA": {"nome": "Cagliari", "regione": "Sardegna"},
	"CL": {"nome": "Caltanissetta", "regione": "Sicilia"},
	"CB": {"nome": "Campobasso", "regione": "Molise"},
	"CI": {"nome": "Carbonia Iglesias", "regione": "Sardegna"},
	"CE": {"nome": "Caserta", "regione": "Campania"},
	"CT": {"nome": "Catania", "regione": "Sicilia"},
	"CZ": {"nome": "Catanzaro", "regione": "Calabria"},
	"CH": {"nome": "Chieti", "regione": "Abruzzo"},
	"CO": {"nome": "Como", "regione": "Lombardia"},
	"CS": {"nome": "Cosenza", "regione": "Calabria"},
	"CR": {"nome": "Cremona", "regione": "Lombardia"},
	"KR": {"nome": "Crotone", "regione": "Calabria"},
	"CN": {"nome": "Cuneo", "regione": "Piemonte"},
	"EN": {"nome": "Enna", "regione": "Sicilia"},
	"FM": {"nome": "Fermo", "regione": "Marche"},
	"FE": {"nome": "Ferrara", "regione": "Emilia Romagna"},
	"FI": {"nome": "Firenze", "regione": "Toscana"},
	"FG": {"nome": "Foggia", "regione": "Puglia"},
	"FC": {"nome": "Forli-Cesena", "regione": "Emilia Romagna"},
	"FR": {"nome": "Frosinone", "regione": "Lazio"},
	"GE": {"nome": "Genova", "regione": "Liguria"},
	"GO": {"nome": "Gorizia", "regione": "Friuli Venezia Giulia"},
	"GR": {"nome": "Grosseto", "regione": "Toscana"},
	"IM": {"nome": "Imperia", "regione": "Liguria"},
	"IS": {"nome": "Isernia", "regione": "Molise"},
	"SP": {"nome": "La-Spezia", "regione": "Liguria"},
	"LT": {"nome": "Latina", "regione": "Lazio"},
	"LE": {"nome": "Lecce", "regione": "Puglia"},
	"LC": {"nome": "Lecco", "regione": "Lombardia"},
	"LI": {"nome": "Livorno", "regione": "Toscana"},
	"LO": {"nome": "Lodi", "regione": "Lombardia"},
	"LU": {"nome": "Lucca", "regione": "Toscana"},
	"MC": {"nome": "Macerata", "regione": "Marche"},
	"MN": {"nome": "Mantova", "regione": "Lombardia"},
	"MS": {"nome": "Massa-Carrara", "regione": "Toscana"},
	"MT": {"nome": "Matera", "regione": "Basilicata"},
	"VS": {"nome": "Medio Campidano", "regione": "Sardegna"},
	"ME": {"nome": "Messina", "regione": "Sicilia"},
	"MI": {"nome": "Milano", "regione": "Lombardia"},
	"MO": {"nome": "Modena", "regione": "Emilia Romagna"},
	"MB": {"nome": "Monza-Brianza", "regione": "Lombardia"},
	"NA": {"nome": "Napoli", "regione": "Campania"},
	"NO": {"nome": "Novara", "regione": "Piemonte"},
	"NU": {"nome": "Nuoro", "regione": "Sardegna"},
	"OG": {"nome": "Ogliastra", "regione": "Sardegna"},
	"OT": {"nome": "Olbia Tempio", "regione": "Sardegna"},
	"OR": {"nome": "Oristano", "regione": "Sardegna"},
	"PD": {"nome": "Padova", "regione": "Veneto"},
	"PA": {"nome": "Palermo", "regione": "Sicilia"},
	"PR": {"nome": "Parma", "regione": "Emilia Romagna"},
	"PV": {"nome": "Pavia", "regione": "Lombardia"},
	"PG": {"nome": "Perugia", "regione": "Umbria"},
	"PU": {"nome": "Pesaro-Urbino", "regione": "Marche"},
	"PE": {"nome": "Pescara", "regione": "Abruzzo"},
	"PC": {"nome": "Piacenza", "regione": "Emilia Romagna"},
	"PI": {"nome": "Pisa", "regione": "Toscana"},
	"PT": {"nome": "Pistoia", "regione": "Toscana"},
	"PN": {"nome": "Pordenone", "regione": "Friuli Venezia Giulia"},
	"PZ": {"nome": "Potenza", "regione": "Basilicata"},
	"PO": {"nome": "Prato", "regione": "Toscana"},
	"RG": {"nome": "Ragusa", "regione": "Sicilia"},
	"RA": {"nome": "Ravenna", "regione": "Emilia Romagna"},
	"RC": {"nome": "Reggio-Calabria", "regione": "Calabria"},
	"RE": {"nome": "Reggio-Emilia", "regione": "Emilia Romagna"},
	"RI": {"nome": "Rieti", "regione": "Lazio"},
	"RN": {"nome": "Rimini", "regione": "Emilia Romagna"},
	"Roma": {"nome": "Roma", "regione": "Lazio"},
	"RO": {"nome": "Rovigo", "regione": "Veneto"},
	"SA": {"nome": "Salerno", "regione": "Campania"},
	"SS": {"nome": "Sassari", "regione": "Sardegna"},
	"SV": {"nome": "Savona", "regione": "Liguria"},
	"SI": {"nome": "Siena", "regione": "Toscana"},
	"SR": {"nome": "Siracusa", "regione": "Sicilia"},
	"SO": {"nome": "Sondrio", "regione": "Lombardia"},
	"TA": {"nome": "Taranto", "regione": "Puglia"},
	"TE": {"nome": "Teramo", "regione": "Abruzzo"},
	"TR": {"nome": "Terni", "regione": "Umbria"},
	"TO": {"nome": "Torino", "regione": "Piemonte"},
	"TP": {"nome": "Trapani", "regione": "Sicilia"},
	"TN": {"nome": "Trento", "regione": "Trentino Alto Adige"},
	"TV": {"nome": "Treviso", "regione": "Veneto"},
	"TS": {"nome": "Trieste", "regione": "Friuli Venezia Giulia"},
	"UD": {"nome": "Udine", "regione": "Friuli Venezia Giulia"},
	"VA": {"nome": "Varese", "regione": "Lombardia"},
	"VE": {"nome": "Venezia", "regione": "Veneto"},
	"VB": {"nome": "Verbania", "regione": "Piemonte"},
	"VC": {"nome": "Vercelli", "regione": "Piemonte"},
	"VR": {"nome": "Verona", "regione": "Veneto"},
	"VV": {"nome": "Vibo-Valentia", "regione": "Calabria"},
	"VI": {"nome": "Vicenza", "regione": "Veneto"},
	"VT": {"nome": "Viterbo", "regione": "Lazio"}
	}


def prov_name2prov_code(prov_name):
	for code in province_codes:
		if province_codes[code]["nome"].upper() == prov_name.upper():
			return code
	return ""