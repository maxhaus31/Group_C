# Welcome to project Okavango
---

## Scenario

Your group is participating in a two-day hackathon where the goal is developing a light-weight data analysis tool that will be used in environmental protection using the **MOST RECENT DATA AVAILABLE**.

## Goal

For this project, we will be using data from [Our World in Data](https://www.ourworldindata.org). The datasets can be found in:

1. [Anual Change in forest area](https://ourworldindata.org/deforestation)
1. [Annual deforestation](https://ourworldindata.org/deforestation)
1. [Share of land that is protected](https://ourworldindata.org/sdgs/life-on-land)
1. [Share of land that is degraded](https://ourworldindata.org/sdgs/life-on-land)
1. [A fifth dataset you find relevant](https://ourworldindata.org/sdgs/life-on-land)
1. [Map dataset: Admin 0 – Countries; Download Countries](https://www.naturalearthdata.com/downloads/110m-cultural-vectors/)

A little help for the latter file:
```bash
import geopandas as gpd
world = gpd.read_file("ne_110m_admin_0_countries.zip")
```

Go over the datasets with your group. Check the info on the website before you start. 

<div class="alert alert-danger">
    <b> THE MOST IMPORTANT TOOLS FOR A DATA SCIENTIST ARE PATIENCE AND COMMUNICATION</b>
    <br>
    <b> Discuss the contents of the datasets with your colleagues. Understanding the data is a priority. </b>
</div>

Use whatever python tools you find apropriate.

## Structure of the project

You are going to build a **[Streamlit app](https://streamlit.io/)** that will showcase your analysis.  
Since you are also using geographical data, you will be using [geopandas](https://geopandas.org).
Use a project structure like this:

```bash
|__downloads/
|__app
|    |__your .py files here
|__tests
|    |__your test files here
|__notebooks
|    |__your notebooks here
|__.gitignore
|__README.md
|__LICENSE.md
|__main.py
```

### Day 1, Phase 1

- One of you will create a github repository (it does not matter who). __THE NAME OF THE REPOSITORY MUST BE "Group_X" where X is the letter of the group! Use a capital letter!__
- Initialize the repo with a README.md file, a proper license, and a .gitignore for the programming language you will use. The README.md file __MUST__ have your emails in a way that it is possible to copy and paste it into outlook.
- The one who created the repository will then give __Maintainer__ permissions to the rest of the group. Check under "Project Information" > "Members".
- [ ] Every element of the group clones the repository to their own laptops.

### Day 1, Phase 2, the data

- [ ] Create a python function (**Function 1**, but you'll have to call it something else) that downloads all the required datasets into the `downloads` directory.
- [ ] Create another function (**Function 2**, again, call it something PEP8 compatible) that merges the map with the datasets. Use `geopandas`. Make sure the left dataframe is the `geopandas` dataframe. See if there are changes needed in order for the merges to work.
- [ ] You decide the create a Class to better handle the data for the project. All names you use __must be PEP8 compliant, like the entire project__.
- [ ] Make a test for Function 1 and one for Function 2, in the appropriate place. If one runs **pytest** in the main directory of the project, all the tests must run.

Now it is time to integrate the functions in a class. The class will have several methods, which you will __not__ develop in the master branch in git.  
Document everything!  
Make your calls compliant with __pydantic__ and __static type checking__ when appliable.

- [ ] Integrate Functions 1 and 2 in your class: During the _init_ method, both functions are execured.
- [ ] The _init_ method must also read the datasets into corresponding dataframes which become attributes for your class.

### Day 1, Phase 3, the app itself

- [ ][ ][ ] Make a Streamlit App where you import your __Class__ and plot the maps. About your streamlit app...
        * It should have a way to select which map to plot. Each map is one of the geopandas dataframes. Only one map at the time.
        * It should plot a graph below the world map. According to each dataset you have, plot the most appropriate information you find, like an histogram of the top 5 countries and bottom 5 countries with annual changes in forest area.

**If you feel lost, don't hesitate to contact me.**

<div class="alert alert-info">
    <b> REMEMBER: THE MOST RECENT DATA AVAILABLE! IT MUST NOT BE HARDCODED!</b>
</div>


<div class="alert alert-info">
    <b> REMEMBER: The first delivery is until March 2 23:59:59 and it is not graded. It is used as course correction. The delivery is the git repo link on moodle. </b>
</div>


<div class="alert alert-info">
    <b> REMEMBER: IT IS OK TO PROTOTYPE CODE IN NOTEBOOKS, BUT THE CLASS MUST BE IN A SINGLE .py FILE! </b>
    <br>
    <b> Prototyping notebooks must have their own separate directory.</b>
    <br>
    <b> We will only consider contents in your "master" repository.</b>
</div>

<div class="alert alert-warning">
    <b>When in doubt, ask.</b>
</div>