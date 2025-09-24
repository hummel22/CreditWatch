# Project to-do list


- [x] Add semiannual options to benefits.
- [x] Benefits box should be collapsible and expandable.
- [x] Add benefit should be popup dialog.
- [x] Add credit card should be popup dialog.
- [x] Add company name to card (Chase, Amex, etc.).
- [x] Add incremental options to benefit (not all used at once)
    - [x] should create a list of uses(find a better name) (add names, date and value)
    - [x] view history , click and show table of histroy in popup
- [x] Add cumulative benefit type
    - [x] no intial value
    - [x] add a use (find a better name)  by hitting a button (add names, date and value)
    - [x] view history , click and show table of histroy in popup
- [x] Preconfigured Cards 
    - [x] in backend/data/creditcards/*.json
    - [x] create schema to store card types (Amex Platinum) and preconfigured benefits and AF fee
    - [x] Cards tp start with
        - [x] Chase Southwest Premiere Business 
        - [x] Chase Ink preferred  
        - [x] Chase Freedom
        - [x] Chase Southwest Premiere
        - [x] Chase IHG Premiere
        - [x] Chase Marriot Boundless
        - [x] Chase Sapphire Reserve
        - [x] hase United Club Car
        - [x] Chase Aeroplan
        - [x] Amex Platinum
        - [x] Capitoal One Venture X
- [x] History
    - [x] Each Credit UI Card should be showing the current year
    - [x] The current year is defined as either the time year bound be the AF due date or the calander year
    - [x] Each year will contain a list of benefits that applied to that year and those benefits will track the use history for that year
    - [x] Add option on card to set AF year or caldner year
    - [x] Add edit pencil icon to top rigt corner of cards and open update dialog box to edit credit card
    - [x] to the left of the pencil icon add a graph icon, hover will show history
    - [x] the histroy icon will open a new popup that will display a credit UI Card for each year that histroy is available for
- [x] Benefits should have an edit icon in the top right that opens a dialog to edit the benefit
- [x] recurring benefits will also have a histoy icon that will show a pop dialog with benefit UI card for each time window in that Credit card year.
- [x] the monthly, quartly and semiannual options should default the expiration dates unless a differnt date is provided (end of month, middle of year, quartarly dates, etc,) annual should have option to reset on year of on AF
- [ ] Create a Header  Bar and then add add an admin page to the board. The admin board should be able to edit and add to prebuilt credit card configutations. these changes should update the .json files
- [ ] Update the (edit,delete, history) icons to have a flat one color icon look
- [ ] Benefits that are recurring should track the total value of the year and also the value for that month
- [ ] The "View History"  should just be a hambuger icon
- [ ] the benefits should take up two columns in a credit UI card
- [ ] when adding a benefit add descripts for standard and incremental , just like there is for cumulative
- [ ] For cumulative add an optional expected value





