FilterParams
------------
Author: kari.kujansuu@gmail.com<br>
September 2021

Gramps add-on that displays the contents and structure of custom filters and allows changing parameters in one screen.

For details on custom filters, see https://gramps-project.org/wiki/index.php/Gramps_5.1_Wiki_Manual_-_Filters#Custom_Filters

### Rationale and purpose

Custom filters is a powerful feature of Gramps. The custom filters are built using built-in or third party rules as building blocks. Filters can also use other filters and such nesting can be arbitrarily deep. There is no feature in standard Gramps that would allow seeing the complete structure of a custom filter at a glance. This tool aims to help.

Any rule used by a filter can have parameters. These parameters can be changed by the user before running a filter but this can be quite cumbersome because the relevant parameters can be in a deeply nested filter possibly in a different category. In that case the user would have to first go to another category, find the correct filter and the rule and change the parameter there - and then return to the actual category and filter to perform the operation. This tool allows changing the parameters in one screen that can also remain active while the user is running the filter. That makes running the filter with varying parameters easier.

The tool also automatically synchronizes certain identical parameters so the user does not need to change the same parameter multiple times. See [ID linking](#id-linking)

### Installation

Install the add-on either manually (https://gramps-project.org/wiki/index.php/5.1_Addons#Manually_installed_Addons) or using the instructions here: https://github.com/Taapeli/isotammi-addons

### Usage

Go to the desired category (People, Families etc). Select the FilterParams tool from the Gramps menu (Tools > Isotammi tools > FilterParams). You will see this window:

![FilterParams](FilterParams.png)

The first dropdown list contains all categories, the default is the current category. The second dropdown list contains all custom filters for the selected category. The first filter in the list is shown by default. Selecting another one will show its contents, for example

![FilterParams](FilterParams2.png)

If a filter is using another filter then the contents of that filter is also shown in an embedded frame. The colors are intended to help in visualizing the structure.

Any parameters are shown in a similar manner as in the regular filter rule editor. Change any parameters and press "Update" - the new values are stored permanently with the filter.

This tool does not otherwise allow editing of the filters or rules (like adding or deleting filters or rules). For those you have to use the regular filter editor. If filters are changed then you should close and reopen the tool - the filter information is not updated dynamically.

#### Common usage tip

A convenient way to use the tool is to open the same filter simultaneously in this tool and in the sidebar filter gramplet. Any parameter change made using this tool is then immediately used by the sidebar filter:

![FilterParams](FilterParams3.png)

It is also probably a good idea to name the filters generically, like above: "In place X" - not "In Florida". This makes changing the parameters more natural.

### Other features

#### ID linking

A filter can contain the same ID parameter in several places. For example, this filter finds the grandparents of a person:

![FilterParams-grandparents](FilterParams-grandparents.png)

The ID of the specified person needs to be in two places in the filter. The tool recognizes this and "links" those parameters with each other. Only the first parameter is editable - the other is disabled and dimmed. If you change the first one then the same value is automatically propagated to the other one. The update is also done immediately and you do not need to press "Update".

The linking happens only if the ID values are initially the same.

This feature works for all "ID" type parameters: persons, families, places etc. It works also if there are more than two identical parameters or is there are multiple sets of such parameters (although this is probably quite rare). 

If you need the IDs to be different then you must change the values using the Gramps standard filter editor.

#### Browsing

You can browse through all filters for a category quickly by using the up and down arrow keys.

#### Tooltips

If a custom filter has a comment then the comment is shown as a tooltip when one hovers the mouse over the filter. For individual rules their name and description are displayed.

#### Filter options

The "invert" check box indicates the option "Return values that do not match the filter rules".

The "All/At least one/Exactly one rule must apply" selection appears only if there actually are multiple rules in a filter.