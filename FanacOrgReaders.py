from bs4 import BeautifulSoup
from bs4 import NavigableString
import requests
import collections
import Helpers
import re
import roman
import FanacDate
import FanacSerial

# ============================================================================================
def ReadFanacFanzineIssues(fanacDirectories):
    # Read index.html files on fanac.org
    # We have a dictionary containing the names and URLs of the 1942 fanzines.
    # The next step is to figure out what 1942 issues of each we have on the website
    # We do this by reading the fanzines/<name>/index.html file and then decoding the table in it.
    # What we get out of this is a list of fanzines with name, URL, and issue info.
    # Loop over the list of all 1942 fanzines, building up a list of those on fanac.org
    print("----Begin reading index.html files on fanac.org")

    global g_browser
    g_browser=None
    fanacIssueInfo=[]

    keys=sorted(list(fanacDirectories.keys()))    # Note that using a dictionary eliminates the consequences of duplicate entries on the Classic, Modern and Electronic pages
    for key in keys:
        title, dirname=fanacDirectories[key]
        Helpers.Log(dirname+",      '"+title+"' --> '"+key+"'", True)

        unskippers=[
            "MT_Void",
        ]
        skippers=[
            #"Australian Science Fiction Bullsheet, The",
            #"Bullsheet",
            "Plokta",
            "Vapourware",
            "Wastebasket"
        ]
        if dirname in skippers:
            Helpers.Log(dirname+"      ***Skipping because it is in skippers", True)
            continue

        if dirname.startswith("http://"):
            Helpers.Log(dirname+"      ***skipped because the index page pointed to is not on fanac.org", True)
            continue

        #if dirname not in unskippers:
         #   continue

        # The URL we get is relative to the fanzines directory which has the URL fanac.org/fanzines
        # We need to turn relPath into a URL
        url=Helpers.RelPathToURL(dirname)
        if url is None:
            continue
        if not url.startswith("http://www.fanac.org"):
            Helpers.Log(url+"    ***skipped because not a fanac.org url", True)
            continue

        if url.startswith("http://www.fanac.org//fan_funds") or url.startswith("http://www.fanac.org/fanzines/Miscellaneous"):
            Helpers.Log(url+"    ***skipped because in the fan_funds or fanzines/Miscellaneous directories", True)
            continue

        ReadAndAppendFanacFanzineIndexPage(title, url, fanacIssueInfo)

    # Now fanacIssueList is a list of all the issues of fanzines on fanac.org which have at least one 1942 issue.(Not all of the issues are 1942.)
    print("----Done reading index.html files on fanac.org")
    if g_browser is not None:
        g_browser.quit()

    return fanacIssueInfo


#=============================================================================================
# Given a list of column headers and a list of row cell values, return the cell matching the header
# If cellname is a list of names, try them all and return the first that hits
def GetCellValueByColHeader(columnHeaders, row, cellnames):

    if type(cellnames) is list:
        for i in range(0, len(columnHeaders)):
            for cn in cellnames:
                if columnHeaders[i].lower() == cn.lower():
                    return row[i]
    else:
        for i in range(0, len(columnHeaders)):
            if columnHeaders[i].lower() == cellnames.lower():
                return row[i]

    return None


#=============================================================================================
# Extract a date from a table row
# We return a tuple: (yearInt, yearText, monthInt, monthText, dayInt, dayText)
def ExtractDate(columnHeaders, row):

    # Does this have a Date column?
    dateText=GetCellValueByColHeader(columnHeaders, row, "Date")
    if dateText is not None and len(dateText) > 0:
        # Get the date
        try:
            return FanacDate.FanacDate().Parse(dateText)
        except:
            pass
        Helpers.Log("      ***Date failure, date='"+dateText+"'", True)
        return FanacDate.FanacDate()

    else:
        # Figure out how to get a year
        yearText=GetCellValueByColHeader(columnHeaders, row, "Year")
        yearInt=FanacDate.InterpretYear(yearText)

        # Now month
        monthText=GetCellValueByColHeader(columnHeaders, row, "Month")
        monthInt=FanacDate.InterpretMonth(monthText)

        # And day
        dayText=GetCellValueByColHeader(columnHeaders, row, "Day")
        dayInt=FanacDate.InterpretDay(dayText)

    d=FanacDate.FanacDate()
    d.Set6(yearText, yearInt, monthText, monthInt, dateText, dayInt)

    mo=monthText.strip() if monthText is not None else ""
    da=dayText.strip() if dayText is not None else ""
    ye=yearText.strip() if yearText is not None else ""

    # We don't have a raw date string here, so we need to synthesize one
    if Helpers.IsNumeric(mo) and Helpers.IsNumeric(da):
        d.Raw=mo+"/"+da+"/"+ye
    elif not Helpers.IsNumeric(mo) and Helpers.IsNumeric(da):
        d.Raw=mo+" "+da+", "+ye
    elif Helpers.IsNumeric(mo) and da == "":
        d.Raw=FanacDate.MonthName(int(mo))+" "+ye
    else:
        d.Raw=(mo+" ").lstrip()+(da+" ").lstrip()+ye        # The lstrip() gets rid of the extra space if mo or da is null

    return d


#=============================================================================================
# Extract a serial number (vol, num, whole_num) from a table row
# We return a tuple: (vol, num)
# Some fanzines have a whole number --> returned as VolNone, Num=nnn
# Others have a Volume and a number --> returned as Vol=nn, Num=nn
# Sometimes the number is composite V2#3 and stored who-knows-where and we gotta find it.
def ExtractSerial(columnHeaders, row):

    wholeText=GetCellValueByColHeader(columnHeaders, row, "Whole")
    volText=GetCellValueByColHeader(columnHeaders, row, "Volume")
    numText=GetCellValueByColHeader(columnHeaders, row, "Number")
    volNumText=GetCellValueByColHeader(columnHeaders, row, "VolNum")
    if type(volNumText) is tuple:
        volNumText=volNumText[0]

    wholeInt=None
    volInt=None
    numInt=None
    maybeWholeInt=None

    #TODO: Need to deal with hyphenated volume and issue numbers, e.g.,  3-4
    #TODO: Need to deal with things like 25A
    if wholeText is not None:
        try:
            wholeInt=int(wholeText)
        except:
            if wholeText is not None and len(wholeText) > 0:
                print("*** Uninterpretable Whole number: '"+str(wholeText)+"'")
            wholeInt=None

    if volNumText is not None:
        ser=FanacSerial.InterpretSerial(volNumText)
        if ser.Vol is not None and ser.Num is not None: # Otherwise, we don't actually have a volume+number
            volInt=ser.Vol
            numInt=ser.Num

    if volText is not None:
        try:
            volInt=int(volText)
        except:
            # Maybe it's in Roman numerals?
            try:
                volInt=roman.fromRoman(volText.upper())
            except:
                if volText is not None and len(volText) > 0:
                    print("*** Uninterpretable Vol number: '"+str(volText)+"'")
                volInt=None

    # If there's no vol, anything under "Num", etc., must actually be a whole number
    if volText is None:
        try:
            maybeWholeText=numText
            maybeWholeInt=int(maybeWholeText)
            numText=None
        except:
            pass

    # But if the *is* a volume specified, than any number not labelled "whole" must be a number within the volume
    if volText is not None and numText is not None:
        try:
            numInt=int(numText)
        except:
            if numText is not None and len(numText) > 0:
                print("*** Uninterpretable Num number: '"+str(numText)+"'")
            numInt=None

    # OK, now figure out the vol, num and whole.
    # First, if a Vol is present, and an unambigious num is absent, the an ambigious Num must be the Vol's num
    if volInt is not None and numInt is None and maybeWholeInt is not None:
        numInt=maybeWholeInt
        maybeWholeInt=None

    # If the wholeInt is missing and maybeWholeInt hasn't been used up, make it the wholeInt
    if wholeInt is None and maybeWholeInt is not None:
        wholeInt=maybeWholeInt
        maybeWholeInt=None

    # Next, look at the title -- titles often have a serial designation at their end.
    titleText=GetCellValueByColHeader(columnHeaders, row, ["Title", "Issue"])
    if titleText is not None:
        # Possible formats:
        #   n   -- a whole number
        #   n.m -- a decimal number
        #   Vn  -- a volume number, but where's the issue?
        #   Vn[,] #m  -- a volume and number-within-volume
        #   Vn.m -- ditto
        if type(titleText) is tuple:
            ser=FanacSerial.InterpretSerial(titleText[0])
        else:
            ser=FanacSerial.InterpretSerial(titleText)

        if ser.Vol is not None and ser.Num is not None:
            if volInt is None:
                volInt=ser.Vol
            if numInt is None:
                numInt=ser.Num
            if volInt != ser.Vol or numInt != ser.Num:
                print("***Inconsistent serial designations: "+str(volInt)+"!="+str(v)+"  or  "+str(numInt)+"!="+str(ser.Num))
        elif ser.Num is not None:
            if wholeInt is None:
                wholeInt=ser.Num
            if wholeInt != ser.Num:
                print("***Inconsistent serial designations."+str(wholeInt)+"!="+str(ser.Num))

    return FanacSerial.FanacSerial(volInt, numInt, wholeInt)


#============================================================================================
def ExtractPageCount(columnHeaders, row):

    pageText=GetCellValueByColHeader(columnHeaders, row, ["Pages", "Pp.", "Page"])
    if pageText is None:
        return 0

    try:
        return int(pageText)
    except:
        return 0


# ============================================================================================
# Fine the cell contaning the issue name
def FindIssueCell(columnHeaders, row):
    # Now find the column containing the issue designation. It could be "Issue" or "Title"
    issueCell=GetCellValueByColHeader(columnHeaders, row, "Issue")
    if issueCell is None:
        issueCell=GetCellValueByColHeader(columnHeaders, row, "Title")
    if issueCell is None:
        issueCell="<not found>"

    return issueCell


# ============================================================================================
# Scan the row and locate the issue cell, title and href and return them as a tuple
def ExtractHrefAndTitle(columnHeaders, row):

    issueCell=FindIssueCell(columnHeaders, row)

    # First, extract the href, if any, leaving the name
    if type(issueCell) is tuple:
        name, href=issueCell
        if href is None:
            href=None
        if name is None:
            name=None
    else:
        name=issueCell
        href=None

    if href is not None:
        return name, href

    # Sometimes the title of the fanzine is in one column and the hyperlink to the issue in another.
    # If we don't find a hyperlink in the title, scan the other cells of the row for a hyperlink
    if href is None and name is not None:
        for i in range(0, len(columnHeaders)):
            if type(row[i]) is tuple:
                n, h=row[i]
                if h is not None:
                    href=h
                    break

    return name, href



FanacIssueInfo=collections.namedtuple("FanacIssueInfo", "FanzineName  FanzineIssueName  Serial  DirectoryURL URL Date Pages")

# ============================================================================================
# Function to extract information from a fanac.org fanzine index.html page
def ReadAndAppendFanacFanzineIndexPage(fanzineName, directoryUrl, fanzineIssueList):
    global g_browser

    print("   ReadAndAppendFanacFanzineIndexPage: "+fanzineName+"   "+directoryUrl)
    # Fanzines with only a single page rather than an index.
    # Note that these are directory names
    singletons=["Ah_Sweet_Idiocy", "BNF_of_IZ", "Chanticleer", "Cosmag", "emu", "Enchanted_Duplicator", "Entropy", "Fan-Fare", "FanToSee", "Flight of the Kangaroo, The",
                "Leaflet", "LeeHoffman", "Mallophagan", "Masque", "Monster",
                "NOSFAn", "Planeteer", "Sense_FAPA", "SF_Digest", "SF_Digest_2", "SFSFS", "SpaceDiversions", "SpaceFlight", "SpaceMagazine",
                "Starlight", "SunSpots", "Tails_of_Fandom", "Tomorrow", "Toto", "Vanations", "Vertigo", "WildHair", "Willis_Papers", "Yandro"]

    weirdos=["Legal Rules, The", "NEOSFS Newsletter, Issue 3, The"]

    # We have some pages where we have a tree of pages with specially-flagged fanzine index tables at the leaf nodes.
    # If this is the root of one of them...
    specialBiggies=["Australian Science Fiction Bullsheet, The", "MT Void, The"]
    if fanzineName in specialBiggies:
        ReadSpecialBiggie(directoryUrl, fanzineIssueList, fanzineName)
        return

    # Ignore weirdos for now
    if fanzineName in weirdos:
        return

    # It looks like this is a single level directory.
    soup=OpenSoup(directoryUrl)
    if soup is None:
        return

    # We need to handle singletons specially
    if directoryUrl.endswith(".html") or directoryUrl.endswith(".htm") or directoryUrl.split("/")[-1:][0] in singletons:
        ReadSingleton(directoryUrl, fanzineIssueList, fanzineName, soup)
        return

    # By elimination, this must be an ordinary page, so read it.
    # Locate the Index Table on this page.
    table=LocateIndexTable(directoryUrl, soup)
    if table is None:
        return

    ReadFanzineIndexTable(directoryUrl, fanzineIssueList, fanzineName, table)
    return


#===================================================================================
# The "special biggie" pages are few (only two at the time this ie being written) and need to be handled specially
# The characteristic is that they are a tree of pages which may contain one or more *tagged* fanzine index tables on any level.
# The strategy is to first look for pages at this level, then recursively do the same for any links to a lower level page (same directory)
def ReadSpecialBiggie(directoryUrl, fanzineIssueList, fanzineName):

    soup=OpenSoup(directoryUrl)
    if soup is None:
        return

    # Look for and interpret all flagged tables on this page, and look for links to subdirectories.

    # Scan for flagged tables on this page
    table=LocateIndexTable(directoryUrl, soup)
    if table is not None:
        ReadFanzineIndexTable(directoryUrl, fanzineIssueList, fanzineName, table)

    # Now look for hyperlinks deeper into the directory. (Hyperlinks going outside the directory are not interesting.)
    links=soup.find_all("a")
    for link in links:
        # If it's an html file it's probably worth investigating
        if "href" in link.attrs.keys():     # Some pages have <A NAME="1"> tags which we need to ignore
            url=link.attrs["href"]
            p=re.compile("^[a-zA-Z0-9\-_]*.html$")
            m=p.match(url)
            if m is not None:
                if url.startswith("index") or url.startswith("archive") or url.startswith("Bullsheet1-00") or url.startswith("Bullsheet2-00"):
                    u=Helpers.ChangeFileInURL(directoryUrl, url)
                    ReadSpecialBiggie(u, fanzineIssueList, fanzineName)
    return

#======================================================================================
# Open a directory's index webpage using BeautifulSoup
def OpenSoup(directoryUrl):
    # Download the index.html, which is
    # * The fanzine's Issue Index Table page
    # * A singleton page
    # * The root of a tree with multiple Issue Index Pages
    try:
        h=requests.get(directoryUrl)
    except:
        try:
            h=requests.get(directoryUrl)
        except:
            Helpers.Log(directoryUrl+"      ***failed because it didn't load", True)
            return None

    # Next, parse the page looking for the body
    soup=BeautifulSoup(h.content, "html.parser")
    return soup


#======================================================================================
# Read a singleton-format fanzine page
def ReadSingleton(directoryUrl, fanzineIssueList, fanzineName, soup):
    # Usually, a singleton has the information in the first h2 block
    found=None
    for stuff in soup:
        if stuff.name=="h2":
            found=stuff
            break
    if found is None:
        Helpers.Log("          ***Failed to find date in '"+directoryUrl+"' which is a singleton.", True)
        return
    content=[str(e) for e in found.contents if type(e) is NavigableString]
    # The name is content[0] (usually!)
    # The date is the first line that looks like a date
    date=None
    for c in content:
        if Helpers.InterpretDateString(c) is not None:
            date=Helpers.InterpretDateString(c)
            break
    y=m=d=None
    if date is not None:
        y=date.year
        m=date.month
        d=date.day
    date=FanacDate
    date.Set(str(y), y, str(m), m, str(d), d)
    fi=FanacIssueInfo(FanzineName=fanzineName, FanzineIssueName=content[0], DirectoryURL=directoryUrl, URL="<URL>", Date=date, Serial=FanacSerial.FanacSerial(), Pages=0)
    print("   (singleton): "+str(fi))
    fanzineIssueList.append(fi)
    return

#=========================================================================================
# Read a fanzine's page of any format
def ReadFanzineIndexTable(directoryUrl, fanzineIssueList, fanzineName, table):

    # OK, we probably have the issue table.  Now decode it.
    # The first row is the column headers
    # Subsequent rows are fanzine issue rows
    Helpers.Log(directoryUrl+"\n")

    # Start by creating a list of the column headers.  This will be used to locate information in each row.
    columnHeaders=[]

    # Create a composition of all columns. The header column may have newline eleemnts, so compress them out.
    # Then compress out sizes in the actual column header, make them into a list, and then join the list separated by spaces
    table.contents=[t for t in table.contents if not isinstance(t, NavigableString)]
    if len(table.contents[0])>1:
        columnHeaders=table.contents[0].text.strip()
    columnHeaders=columnHeaders.split("\n")
    columnHeaders=[Helpers.CannonicizeColumnHeaders(c) for c in columnHeaders]

    # We need to pull the fanzine rows in from BeautifulSoup and save them in the same format for later analysis.
    # The format will be a list of rows
    # Each row will be a list of cells
    # Each cell will be either a text string or, if the cell contained a hyperlink, a tuple containing the cell text and the hyperlink
    tableRows=[]
    for i in range(1, len(table)):
        tableRow=Helpers.RemoveNewlineRows(table.contents[i])
        newRow=[]
        for cell in tableRow:
            cellval=Helpers.GetHrefAndTextFromTag(cell)
            if cellval[1] is None:
                newRow.append(cellval[0])
            else:
                newRow.append(cellval)
        tableRows.append(newRow)

    # Now we process the table rows, extracting the information for each fanzine issue.
    for i in range(0, len(tableRows)):
        # We need to skip the column headers
        tableRow=tableRows[i]
        if len(tableRow)==1 and tableRow[0]=="\n":  # Skip empty rows
            continue
        print("   row="+str(tableRow))

        # We need to extract the name, url, year, and vol/issue info for each fanzine
        # We have to treat the Title column specially, since it contains the critical href we need.
        date=ExtractDate(columnHeaders, tableRow)
        ser=ExtractSerial(columnHeaders, tableRow)
        name, href=ExtractHrefAndTitle(columnHeaders, tableRow)
        pages=ExtractPageCount(columnHeaders, tableRow)

        # And save the results
        fi=FanacIssueInfo(FanzineName=fanzineName, FanzineIssueName=name, DirectoryURL=directoryUrl, URL=href, Date=date, Serial=ser, Pages=pages)
        if fi.FanzineIssueName == "<not found>" and fi.Serial.Vol is None and fi.Date.YearInt is None and fi.Date.MonthInt is None:
            Helpers.Log("   ****Skipping null table row: "+str(fi))
            continue

        print("   "+str(fi))
        fanzineIssueList.append(fi)

        # Log it.
        if fi is not None:
            urlT=""
            if fi.URL is None:
                urlT="*No URL*"
            Helpers.Log("      Row "+str(i)+"  '"+str(fi.FanzineIssueName)+"'  ["+fi.Serial.FormatSerial()+"]  ["+fi.Date.FormatDate()+"]  "+urlT)
        else:
            Helpers.Log(fanzineName+"      ***Can't handle "+directoryUrl, True)


#===============================================================================
# Locate a fanzine index table.
def LocateIndexTable(directoryUrl, soup):
    global g_browser

    # Because the structures of the pages are so random, we need to search the body for the table.
    # *So far* nearly all of the tables have been headed by <table border="1" cellpadding="5">, so we look for that.
    table=Helpers.LookForTable(soup, {"border" : "1", "cellpadding" : "5"})
    if table is not None:
        return table

    # A few cases have been tagged explicitly
    table=Helpers.LookForTable(soup, {"class" : "indextable"})
    if table is not None:
        return table

    # Then there's Peon...
    table=Helpers.LookForTable(soup, {"border" : "1", "cellpadding" : "3"})
    if table is not None:
        return table

    # Then there's Bable-On...
    table=Helpers.LookForTable(soup, {"cellpadding" : "10"})
    if table is not None:
        return table

    Helpers.Log(directoryUrl+"      ***failed because BeautifulSoup found no index table in index.html", True)
    return None



