from dataclasses import dataclass, field
import roman
import re

@dataclass()
class FanacSerial:
    Vol: int = None
    Num: int = None
    Whole: int = None

    #=============================================================================================
    # If there's a trailing Vol+Num designation at the end of a string, interpret it.
    # We return a tuple of a (Vol, Num) or a (None, Num)
    # We accept:
    #       ...Vnn[,][ ]#nnn[ ]
    #       ...nn[ ]
    #       ...nnn/nnn[  ]
    #       ...nn.mm
    def InterpretSerial(self, s):

        s=s.upper()

        # First look for a Vol+Num designation
        p=re.compile("(.*)V([0-9]+),?\s*#([0-9]+)\s*$")
        m=p.match(s)
        if m is not None and len(m.groups()) == 2:
            self.Vol=int(m.groups()[0])
            self.Num=int(m.groups()[1])
            return self

        # Now look for nnn/nnn
        p=re.compile("^.*([0-9]+)/([0-9]+)\s*$")
        m=p.match(s)
        if m is not None and len(m.groups()) == 2:
            self.Vol=int(m.groups()[0])
            self.Num=int(m.groups()[1])
            return self

        # Now look for xxx/nnn, where xxx is in Roman numerals
        p=re.compile("^\s*([IVXLC]+)/([0-9]+)\s*$")
        m=p.match(s)
        if m is not None and len(m.groups()) == 2:
            self.Vol=roman.fromRoman(int(m.groups()[0]))
            self.Num=int(m.groups()[1])
            return self

        # Now look for a trailing decimal number
        p=re.compile("^.*\D([0-9]+\.[0-9]+)\s*$")       # the \D demands a non-digit character; it's to stop the greedy parser.
        m=p.match(s)
        if m is not None and len(m.groups()) == 1:
            self.Vol=None
            self.Num=float(m.groups()[0])
            return self

        # Now look for a single trailing number
        p=re.compile("^.*\D([0-9]+)\s*$")
        m=p.match(s)
        if m is not None and len(m.groups()) == 1:
            self.Vol=None
            self.Num=int(m.groups()[0])
            return self

        # No good, return failure
        return self


    #=============================================================================
    # Format the Vol/Num/Whole information
    def FormatSerial(self):
        if self.Whole is not None and self.Whole != 0 and self.Vol is not None and self.Vol !=0 and self.Num is not None and self.Num != 0:
            return "#"+str(self.Whole)+"  (V"+str(self.Vol)+"#"+str(self.Num)+")"

        if self.Whole is not None and self.Whole != 0:
            return "#"+str(self.Whole)

        if self.Vol is None and self.Num is None:
            return ""

        v="?"
        n="?"
        if self.Vol is not None and self.Vol!=0:
            v=str(self.Vol)
        if self.Num is not None and self.Num!=0:
            n=str(self.Num)

        return "V"+v+"#"+n


    # =====================================================================================
    # Function to attempt to decode an issue designation into a volume and number
    # Return a tuple of Volume and Number
    # If there's no volume specified, Volume is None and Number is the whole number
    # If we can't make sense of it, return (None, None), so if the 2nd member of the tuple is None, conversion failed.
    def DecodeIssueDesignation(self, str):
        try:
            return (None, int(str))
        except:
            i=0  # A dummy statement since all we want to do with an exception is move on to the next option.

        # Ok, it's not a simple number.  Drop leading and trailing spaces and see if it of the form #nn
        s=str.strip().lower()
        if len(s)==0:
            return (None, None)
        if s[0]=="#":
            s=s[1:]
            if len(s)==0:
                return (None, None)
            try:
                return (None, int(s))
            except:
                i=0  # A dummy statement since all we want to do with an exception is move on to the next option.

        # This exhausts the single number possibilities
        # Maybe it's of the form Vnn, #nn (or Vnn.nn or Vnn,#nn)

        # Strip any leading 'v'
        if len(s)==0:
            return (None, None)
        if s[0]=="v":
            s=s[1:]
            if len(s)==0:
                return (None, None)

        # The first step is to see if there's at least one of the characters ' ', '.', and '#' in the middle
        # We split the string in two by a span of " .#"
        # Walk through the string until we;ve passed the first span of digits.  Then look for a span of " .#". The look for at least one more digit.
        # Since we've dropped any leading 'v', we kno we must be of the form nn< .#>nnn
        # So if the first character is not a digit, we give up.
        if not s[0].isdigit():
            return (None, None)

        # Now, the only legetimate charcater other than digits are the three delimiters, so translate them all to blanks and then split into the two digit strings
        spl=s.replace(".", " ").replace("#", " ").split()
        if len(spl)!=2:
            return (None, None)
        try:
            return (int(spl[0]), int(spl[1]))
        except:
            return (None, None)


    #==============================================================================
    def ExtractSerial(self, volText, numText, wholeText, volNumText, titleText):
        wholeInt=None
        volInt=None
        numInt=None
        maybeWholeInt=None

        # TODO: Need to deal with hyphenated volume and issue numbers, e.g.,  3-4
        # TODO: Need to deal with things like 25A
        if wholeText is not None:
            try:
                wholeInt=int(wholeText)
            except:
                if wholeText is not None and len(wholeText)>0:
                    print("*** Uninterpretable Whole number: '"+str(wholeText)+"'")
                wholeInt=None

        if volNumText is not None:
            ser=FanacSerial().InterpretSerial(volNumText)
            if ser.Vol is not None and ser.Num is not None:  # Otherwise, we don't actually have a volume+number
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
                    if volText is not None and len(volText)>0:
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
                if numText is not None and len(numText)>0:
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

        if titleText is not None:
            # Possible formats:
            #   n   -- a whole number
            #   n.m -- a decimal number
            #   Vn  -- a volume number, but where's the issue?
            #   Vn[,] #m  -- a volume and number-within-volume
            #   Vn.m -- ditto
            if type(titleText) is tuple:
                ser=FanacSerial().InterpretSerial(titleText[0])
            else:
                ser=FanacSerial().InterpretSerial(titleText)

            # Some indexes have fanzine names ending in <month> <year>.  We'll detect these by looking for a trailing number between 1930 and 2050, and reject
            # getting vol/ser, etc., from the title if we find it.
            if ser.Num is None or ser.Num < 1930 or ser.Num > 2050:

                if ser.Vol is not None and ser.Num is not None:
                    if volInt is None:
                        volInt=ser.Vol
                    if numInt is None:
                        numInt=ser.Num
                    if volInt!=ser.Vol or numInt!=ser.Num:
                        print("***Inconsistent serial designations: "+str(volInt)+"!="+str(v)+"  or  "+str(numInt)+"!="+str(ser.Num))
                elif ser.Num is not None:
                    if wholeInt is None:
                        wholeInt=ser.Num
                    if wholeInt!=ser.Num:
                        print("***Inconsistent serial designations."+str(wholeInt)+"!="+str(ser.Num))

        self.Vol=volInt
        self.Num=numInt
        self.Whole=wholeInt
        return self