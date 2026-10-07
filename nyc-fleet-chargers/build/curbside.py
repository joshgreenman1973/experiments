"""DOT curbside chargers are listed as "Street: cross street, cross street". Each entry here is
(borough, main street, first cross street, second cross street), spelled the way the city's street
centerline file (CSCL) spells them; "|" separates alternate spellings. The charger is placed at the
midpoint of the block between the two corners."""
CURB = {
    '13th Street: 5th Avenue, 4th Avenue': ('BK', '13 ST', '5 AVE', '4 AVE'),
    '225th Street: Merrick Boulevard, 135th Avenue': ('QN', '225 ST', 'MERRICK BLVD', '135 AVE'),
    '30th Pl between Thomson Ave and 47th Ave': ('QN', '30 PL', 'THOMSON AVE', '47 AVE'),
    '33rd Street: 31st Avenue, Broadway': ('QN', '33 ST', '31 AVE', 'BROADWAY'),
    '35th Street: 30th Avenue, 28th Avenue': ('QN', '35 ST', '30 AVE', '28 AVE'),
    '38th Street: 36th Avenue, 35th Avenue': ('QN', '38 ST', '36 AVE', '35 AVE'),
    '3rd Avenue: 33rd Street, 34th Street': ('BK', '3 AVE', '33 ST', '34 ST'),
    '41st Avenue: 81st Street, Baxter Avenue': ('QN', '41 AVE', '81 ST', 'BAXTER AVE'),
    '43rd Street: 5th Avenue, 4th Avenue': ('BK', '43 ST', '5 AVE', '4 AVE'),
    '72nd Street: 37th Avenue, 35th Avenue': ('QN', '72 ST', '37 AVE', '35 AVE'),
    '8th Street: 6th Avenue, 7th Avenue': ('BK', '8 ST', '6 AVE', '7 AVE'),
    'Bedford Park Boulevard: Goulden Avenue, Paul Avenue': ('BX', 'BEDFORD PARK BLVD|BEDFORD PARK BLVD W', 'GOULDEN AVE', 'PAUL AVE'),
    'Broadway: West 242nd Street, West 240th Street': ('BX', 'BROADWAY', 'W 242 ST', 'W 240 ST'),
    'Brooklyn Avenue: St. Marks Avenue, Prospect Place': ('BK', 'BROOKLYN AVE', 'ST MARKS AVE', 'PROSPECT PL'),
    'Clarkson Avenue: 40th Street, Albany Avenue': ('BK', 'CLARKSON AVE', 'E 40 ST', 'ALBANY AVE'),
    'Court Street: 1st Place, Carroll Street': ('BK', 'COURT ST', '1 PL', 'CARROLL ST'),
    'Dekalb Avenue: East Gun Hill Road, East 212th Street': ('BX', 'DEKALB AVE', 'E GUN HILL RD', 'E 212 ST'),
    'East 67th Street: York Avenue, 1st Avenue': ('MN', 'E 67 ST', 'YORK AVE', '1 AVE'),
    'East 78th Street: Park Avenue, Lexington Avenue': ('MN', 'E 78 ST', 'PARK AVE', 'LEXINGTON AVE'),
    'East End Ave: East 88th Street, East 87th Street': ('MN', 'E END AVE', 'E 88 ST', 'E 87 ST'),
    'Elton Street: Flatlands Avenue, Locke Street': ('BK', 'ELTON ST', 'FLATLANDS AVE', 'LOCKE ST'),
    'Fort Washington Avenue: West 164th Street, West 165th Street': ('MN', 'FT WASHINGTON AVE|FORT WASHINGTON AVE', 'W 164 ST', 'W 165 ST'),
    'Lenox Road: New York Avenue, East 34th Street': ('BK', 'LENOX RD', 'NEW YORK AVE', 'E 34 ST'),
    'Leonard St between Lafayette and Centre Streets': ('MN', 'LEONARD ST', 'LAFAYETTE ST', 'CENTRE ST'),
    'Linden Boulevard: East 96th Street, Rockaway Parkway': ('BK', 'LINDEN BLVD', 'E 96 ST', 'ROCKAWAY PKWY'),
    'Marcus Garvey Boulevard: Broadway, Park Avenue': ('BK', 'MARCUS GARVEY BLVD', 'BROADWAY', 'PARK AVE'),
    'Mason Avenue: Seaview, Delaware Avenue': ('SI', 'MASON AVE', 'SEAVIEW AVE', 'DELAWARE AVE'),
    'Meeker Avenue: Metropolitan Avenue, Rodney Street': ('BK', 'MEEKER AVE', 'METROPOLITAN AVE', 'RODNEY ST'),
    'North 4th Street: Bedford Avenue, Berry Street': ('BK', 'N 4 ST', 'BEDFORD AVE', 'BERRY ST'),
    'Norman Avenue: Dobbin Street, Guernsey Street': ('BK', 'NORMAN AVE', 'DOBBIN ST', 'GUERNSEY ST'),
    'Prospect Park West: 5th Street, 6th Street': ('BK', 'PROSPECT PARK W', '5 ST', '6 ST'),
    'Putnam Place: East Gun Hill Rd., Reservoir Oval West': ('BX', 'PUTNAM PL', 'E GUN HILL RD', 'RESERVOIR OVAL W'),
    'Queens Boulevard: 34th Street, 33rd Street': ('QN', 'QUEENS BLVD', '34 ST', '33 ST'),
    'Reade St between Elk and Lafayette Streets': ('MN', 'READE ST', 'ELK ST', 'LAFAYETTE ST'),
    'Red Cross Pl between Cadman Pl E and Bk Bridge Blvd/Adams St': ('BK', 'RED CROSS PL', 'CADMAN PLZ E', 'ADAMS ST|BROOKLYN BRIDGE BLVD'),
    'Stuyvesant Avenue: Fulton Street, Chauncey Street': ('BK', 'STUYVESANT AVE', 'FULTON ST', 'CHAUNCEY ST'),
    'West 76th Street: Amsterdam Avenue, Columbus Avenue': ('MN', 'W 76 ST', 'AMSTERDAM AVE', 'COLUMBUS AVE'),
    'West 84th Street: Amsterdam Avenue, Columbus Avenue': ('MN', 'W 84 ST', 'AMSTERDAM AVE', 'COLUMBUS AVE'),
    'West 93rd Street: Central Park West, Columbus Ave': ('MN', 'W 93 ST', 'CENTRAL PARK W', 'COLUMBUS AVE'),
    # Parks Department lot in Sara D. Roosevelt Park, listed only as "Hester St"
    'Hester St': ('MN', 'HESTER ST', 'CHRYSTIE ST', 'FORSYTH ST'),
}
# single corners: (borough, street, cross street)
CORNER = {
    'Westchester Av/Burr Av': ('BX', 'WESTCHESTER AVE', 'BURR AVE'),
    '10Th Street And Queens Plaza South': ('QN', '10 ST', 'QUEENS PLZ S'),
    # Queens house numbers name the cross street: 47-01 48th Street sits at 47th Avenue
    '47-01 48Th Street': ('QN', '48 ST', '47 AVE'),
    '47-01 48Th St': ('QN', '48 ST', '47 AVE'),
    # Canarsie Park yard listed only as "E 88th St"; E. 88th meets the park at Seaview Avenue
    'E 88th St': ('BK', 'E 88 ST', 'SEAVIEW AVE'),
}
