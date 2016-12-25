# SNeezy
# A SNES emulator front-end for the Raspberry Pi.
# Version 1.0.0
# Jessie Hildebrandt

# Copyright (C) 2016 Jessie Hildebrandt
#
# This file is part of SNeezy.
#
# SNeezy is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# SNeezy is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with SNeezy.  If not, see <http://www.gnu.org/licenses/>.

# Imports!
import yaml
import pygame
import math
import os
import subprocess as sub
import sys
import time
import threading

# Create an empty table/list to store resources/ROMs in.
resources = {}
romList = []

# Load and parse the user-provided settings from the configuration file.
userSettings = yaml.load(file('config.yaml'))

# Load the volume level.
volumeLevel = yaml.load(file('volume.yaml'))['volume']

# Define some variables to be used throughout the menus in the program.
romListOpen = False
currentSelection = 0
currentPage = 0
numberOfPages = 0
currentTemperature = "??.? C"

# Define a short function for closing the program.
def exit():
    
    # Save the volume level before exiting the program.
    print("Saving volume level...")
    open('volume.yaml', 'w').write("volume: " + str(volumeLevel))
    
    # Exit the program.
    sys.exit()

# Define a short function for parsing the color strings provided by the configuration file.
def parseColorString(colorString):
    return tuple([int(value) for value in colorString.split(",")])

# Define a short function for setting the volume of the system.
def setVolume(newVolume):
    global volumeLevel
    volumeLevel = min(100, max(0, newVolume))
    print("amixer -D pule sset Master " + str(volumeLevel) + "%")
    os.system("amixer set PCM " + str(volumeLevel) + "%")
    
# Define a short function for getting the temperature of the system.
def updateTemperature():
    global currentTemperature
    currentTemperature = sub.Popen("/opt/vc/bin/vcgencmd measure_temp | grep -Eo '[0-9]{1,2}.[0-9]{1,2}'", stdout=sub.PIPE, shell=True).communicate()[0].replace('\n', '') + ' C'
    if currentTemperature == "":
        currentTemperature = "??.? C"

# Define a short function for scaling an image down to fit a limiting dimension.
def scaleToFit(image, limitingDimension, fitVertically = True, scaleUp = True):
    w = image.get_width()
    h = image.get_height()
    if fitVertically:
        scale = limitingDimension / float(h)
    else:
        scale = limitingDimension / float(w)
    if scale > 1 and not scaleUp:
        scale = 1
    return pygame.transform.scale(image, (int(w * scale), int(h * scale)))

# Define a function to draw the loading screen. (Also, the shutdown and reboot screens.)
def drawStatusScreen(screen, screenType):

    # Grab the lits of preferred colors from the parsed configuration file.
    colors = userSettings['colors']

    # Fill in the screen with the background color.
    screen.fill(parseColorString(colors['background']))

    # If it's been specified, draw the shutdown or reboot screen. Otherwise, draw the loading screen.
    if screenType == "shutdown":
        screenImage = resources['shutting_down_screen']
    elif screenType == "reboot":
        screenImage = resources['rebooting_screen']
    elif screenType == "load":
        screenImage = resources['loading_screen']

    # Draw in the loading/reboot/shutdown screen.
    screen.blit(screenImage, ((screen.get_width() * 0.5) - (resources['loading_screen'].get_width() * 0.5), 0))

# Define a function to draw the main menu.
def drawMenu(screen):

    # Grab the list of preferred settings and colors from the parsed configuration file.
    settings = userSettings['options']
    colors = userSettings['colors']

    # Fill in the screen with the background color.
    screen.fill(parseColorString(colors['background']))

    # Draw a rectangle for the background of the header at the top of the screen.
    screen.fill(parseColorString(colors['header']), pygame.Rect((0, 0), (screen.get_width(), settings['header_height'] * screen.get_height())))

    # Draw the logo on top of the header.
    screen.blit(resources['logo'], (0, 0))

    # Calculate the dimensions of the menu items.
    headerOffset = settings['header_height'] * screen.get_height() + (settings['item_gap'] * screen.get_height())
    itemW = (screen.get_width() * 0.5) - (settings['item_gap'] * screen.get_width())
    itemH = ((screen.get_height() - headerOffset) * 0.25) - (settings['item_gap'] * screen.get_height())
    itemGap = ((screen.get_height() - headerOffset) * 0.25)

    # Draw all of the buttons.
    buttonText = ["Load ROM", "Volume", "Reboot", "Shutdown"]
    if currentSelection == 1:
        buttonText[1] += ": <- " + str(volumeLevel) + "% ->"
    for button in range(0, len(buttonText)):

        # Change the color if the current button being draw is the highlighted button.
        if currentSelection == button:
            textColor = parseColorString(colors['text_highlighted'])
            color = parseColorString(colors['item_highlighted'])
        else:
            textColor = parseColorString(colors['text'])
            color = parseColorString(colors['item'])

        # Define a rectangle for the button and fill it in.
        buttonRect = pygame.Rect((screen.get_width() * 0.5, headerOffset + (itemGap * button)), (itemW, itemH))
        screen.fill(color, buttonRect)

        # Draw in the text of the button using the same rectangle we defined before.
        screen.blit(resources['font'].render(buttonText[button], False, textColor), (buttonRect.left + settings['font_size'], buttonRect.top + (itemH * 0.5) - (settings['font_size'] * 0.5)))

    # Draw the current temperature in the header.
    temperatureText = scaleToFit(resources['font'].render(str(currentTemperature), False, parseColorString(colors['text'])), settings['header_height'] * screen.get_height(), True, False)
    screen.blit(temperatureText, (screen.get_width() - temperatureText.get_width() - settings['font_size'], (settings['header_height'] * screen.get_height() * 0.5) - (temperatureText.get_height() * 0.5)))

    # Draw a contextual image, depending on what's highlighted.
    menuImage = [resources['play_icon'], resources['volume_icon'], resources['reboot_icon'], resources['shutdown_icon']]
    selectedImage = menuImage[currentSelection]
    screen.blit(selectedImage, ((screen.get_width() * 0.25) - (selectedImage.get_width() * 0.5), ((screen.get_height() - headerOffset) * 0.5 + headerOffset) - (selectedImage.get_height() * 0.5)))

# Define a function to load boxart for the ROM list. (To be used in a thread.)
def loadBoxart(screen):

    # Grab the list of preferred settings from the parsed configuration file.
    settings = userSettings['options']

    # Prepare to handle the global romList variable.
    global romList

    # Loop continuously until the user goes back to the main menu.
    while romListOpen:

        # Calculate the index of the currently selected ROM.
        currentRom = currentPage * settings['roms_per_page'] + currentSelection

        # Load the boxart for the current selection if it hasn't been loaded already.
        if not romList[currentRom]['boxartLoaded']:
            romList[currentRom]['boxartImage'] = scaleToFit(pygame.image.load(romList[currentRom]["boxartPath"]).convert_alpha(), (screen.get_width() * settings['icon_size']), False)
            romList[currentRom]['boxartLoaded'] = True

# Define a function to draw the ROM list.
def drawRomList(screen):

    # Grab the list of preferred settings and colors from the parsed configuration file.
    settings = userSettings['options']
    colors = userSettings['colors']

    # Fill in the screen with the background color.
    screen.fill(parseColorString(colors['background']))

    # Draw a rectangle for the background of the header at the top of the screen.
    screen.fill(parseColorString(colors['header']), pygame.Rect((0, 0), (screen.get_width(), settings['header_height'] * screen.get_height())))

    # Draw the logo on top of the header.
    screen.blit(resources['logo'], (0, 0))

    # Calculate the dimensions of the ROM labels.
    headerOffset = settings['header_height'] * screen.get_height() + (settings['item_gap'] * screen.get_height())
    itemW = (screen.get_width() * 0.5) - (settings['item_gap'] * screen.get_width())
    itemH = ((screen.get_height() - headerOffset) * (1 / float(settings['roms_per_page']))) - (settings['item_gap'] * screen.get_height())
    itemGap = (screen.get_height() - headerOffset) * (1 / float(settings['roms_per_page']))

    # Calculate how many ROMs are going to be displayed.
    buttonsToDraw = settings['roms_per_page']
    if currentPage == numberOfPages - 1 and not len(romList) % settings['roms_per_page'] == 0:
        buttonsToDraw = len(romList) % settings['roms_per_page']

    # Calculate which ROM titles are going to be displayed.
    buttonText = ['None'] * buttonsToDraw
    for button in range(0, buttonsToDraw):
        buttonText[button] = romList[currentPage * settings['roms_per_page'] + button]['title']

    # Draw the buttons for each ROM.
    for button in range(0, buttonsToDraw):

        # Change the color if the current button being draw is the highlighted button.
        if currentSelection == button:
            textColor = parseColorString(colors['text_highlighted'])
            color = parseColorString(colors['item_highlighted'])
        else:
            textColor = parseColorString(colors['text'])
            color = parseColorString(colors['item'])

        # Define a rectangle for the button and fill it in.
        buttonRect = pygame.Rect((screen.get_width() * 0.5, headerOffset + (itemGap * button)), (itemW, itemH))
        screen.fill(color, buttonRect)

        # Draw in the text of the button using the same rectangle we defined before.
        renderedTitle = scaleToFit(resources['font'].render(buttonText[button], False, textColor), buttonRect.height, True, False)
        screen.blit(
            renderedTitle,
            (buttonRect.left + settings['font_size'], buttonRect.top + (itemH * 0.5) - (renderedTitle.get_height() * 0.5)),
            pygame.Rect(0, 0, buttonRect.width - settings['font_size'] * 2, buttonRect.height))

    # Draw the page number and ROM count in the header.
    ROMCount = scaleToFit(resources['font'].render(str(currentPage * settings['roms_per_page'] + currentSelection + 1) + "/" + str(len(romList)), False, parseColorString(colors['text'])), settings['header_height'] * screen.get_height(), True, False)
    screen.blit(
        ROMCount,
        (screen.get_width() - ROMCount.get_width() - settings['font_size'], (settings['header_height'] * screen.get_height() * 0.5) - (ROMCount.get_height() * 0.5)))

    # Draw the boxart image.
    boxartImage = romList[currentPage * settings['roms_per_page'] + currentSelection]['boxartImage']
    screen.blit(boxartImage, ((screen.get_width() * 0.25) - (boxartImage.get_width() * 0.5), ((screen.get_height() - headerOffset) * 0.5 + headerOffset) - (boxartImage.get_height() * 0.5)))
    screen.blit(resources['cartridge_icon'], ((screen.get_width() * 0.25) - (boxartImage.get_width() * 0.5), ((screen.get_height() - headerOffset) * 0.5 + headerOffset) - (boxartImage.get_height() * 0.5)))
    

# Define a function that handles changes in the menu selection.
def changeSelection(direction, jumpPage = False):

    # Handle the global currentSelection, currentPage and selectedRom variables.
    global currentSelection, currentPage, selectedRom

    # Grab the list of program options from the parsed configuration file.
    settings = userSettings['options']

    # If we're on the main menu, handle the selection change for the menu.
    if not romListOpen:
        
        # If we're going up, make sure we're not at the top. If we are, wrap around.
        if direction == "up":
            if currentSelection <= 0:
                currentSelection = 3
            else:
                currentSelection = currentSelection -1

        # Ditto for going down.
        elif direction == "down":
            if currentSelection >= 3:
                currentSelection = 0
            else:
                currentSelection = currentSelection + 1

    # Otherwise, handle the selection change for the more complicated ROM list menu.
    else:

        # Going up!
        if direction == "up":

            # If we're going up one item, make sure we're not at the top. If we are, go up a page.
            if not jumpPage:
                if currentSelection <= 0 and currentPage > 0:
                    currentSelection = settings['roms_per_page'] - 1
                    currentPage -= 1
                elif currentSelection > 0:
                    currentSelection -= 1

            # If we're going up one page, make sue we're not at the top page. If we aren't, go up a page.
            else:
                if currentPage > 0:
                    currentPage -= 1

        # Going down!
        elif direction == "down":

	    # There may be an odd number of buttons on the page, so we'll need to calculate the number of buttons here.
            buttonsOnPage = settings['roms_per_page']
            if currentPage == numberOfPages - 1 and not len(romList) % settings['roms_per_page'] == 0:
                buttonsOnPage = len(romList) % settings['roms_per_page']

            # If we're going down one item, make sure we're not scrolling past the last item on the page.
            if not jumpPage:
                if currentSelection >= buttonsOnPage - 1 and currentPage < numberOfPages - 1:
                    currentSelection = 0
                    currentPage += 1
                elif currentSelection < buttonsOnPage - 1:
                    currentSelection += 1

            # If we're going down on page, make sure we're not at the bottom page. If we aren't, go down a page.
            else:
                if currentPage < numberOfPages - 1:
		    if currentSelection >= buttonsOnPage - 1:
                        currentSelection = buttonsOnPage - 1
                    currentPage += 1

# Define a function to handle controller input and events.
def handleInput(events, screen):

    # Handle the global currentSelection, currentPage, selectedRom and romListOpen variables.
    global currentSelection, currentPage, romListOpen

    # Grab the list of program options from the parsed configuration file.
    settings = userSettings['options']

    # Sift through each event in the event queue.
    for event in events:
        
    	# If our temperature timer went off, update the temperature.
    	if event.type == pygame.USEREVENT + 1:
    	    updateTemperature()
            
        # If we're on the main menu, handle events for the menu. This next bit is really rough and needs touching-up in the future.
        if not romListOpen:

            # Keyboard input!
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_w:
                    changeSelection("up")
                elif event.key == pygame.K_s:
                    changeSelection("down")
                elif event.key == pygame.K_a:
                    if currentSelection == 1:
                        if volumeLevel >= 10:
                            setVolume(volumeLevel - 10)
                elif event.key == pygame.K_d:
                    if currentSelection == 1:
                        if volumeLevel <= 90:
                            setVolume(volumeLevel + 10)
                elif event.key == pygame.K_RETURN:
                    if currentSelection == 0:
                        romListOpen = True
                        if settings['threaded_boxart_loader'] and settings['load_boxart']:
                            threading.Thread(target=loadBoxart, args=(screen,)).start()
                            currentPage = 0
                    elif currentSelection == 2:
                        drawStatusScreen(screen, 'reboot')
                        pygame.display.flip()
                        os.system('resources/scripts/reboot.sh')
                    elif currentSelection == 3:
                        drawStatusScreen(screen, 'shutdown')
                        pygame.display.flip()
                        os.system('resources/scripts/shutdown.sh')
                elif event.key == pygame.K_ESCAPE:
                    pygame.quit()
                    exit()

            # Joystick axis input!
            elif event.type == pygame.JOYAXISMOTION:
                if event.dict['axis'] == 1 and event.dict['value'] < 0:
                    changeSelection("up")
                elif event.dict['axis'] == 1 and event.dict['value'] > 0:
                    changeSelection("down")
                elif event.dict['axis'] == 0 and event.dict['value'] < 0:
                    if currentSelection == 1:
                        if volumeLevel >= 10:
                            setVolume(volumeLevel - 10)
                elif event.dict['axis'] == 0 and event.dict['value'] > 0:
                    if currentSelection == 1:
                        if volumeLevel <= 90:
                            setVolume(volumeLevel + 10)

            # Joystick button input!
            elif event.type == pygame.JOYBUTTONDOWN:
                if event.button == 6:
                    changeSelection("down")
                if event.button == 0 or event.button == 7:
                    if currentSelection == 0:
                        romListOpen = True
                        if settings['threaded_boxart_loader'] and settings['load_boxart']:
                            threading.Thread(target=loadBoxart, args=(screen,)).start()
                            currentPage = 0
                    elif currentSelection == 2:
                        drawStatusScreen(screen, 'reboot')
                        pygame.display.flip()
                        os.system('resources/scripts/reboot.sh')
                    elif currentSelection == 3:
                        drawStatusScreen(screen, 'shutdown')
                        pygame.display.flip()
                        os.system('resources/scripts/shutdown.sh')

        # If we're on the ROM list, handle events for the ROM list.
        else:

            # Keyboard input!
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_w:
                    changeSelection("up")
                elif event.key == pygame.K_s:
                    changeSelection("down")
                elif event.key == pygame.K_a:
                    changeSelection("up", True)
                elif event.key == pygame.K_d:
                    changeSelection("down", True)
                elif event.key == pygame.K_RETURN:
                    print("Loading: " + romList[currentPage * settings['roms_per_page'] + currentSelection]['title'])
                    pygame.quit()
                    time.sleep(1)
                    os.system(settings['emulator_path'] + ' "' + romList[currentPage * settings['roms_per_page'] + currentSelection]['fullPath'] + '"')
                    exit()
                elif event.key == pygame.K_ESCAPE:
                    romListOpen = False
                    currentSelection = 0

            # Joystick axis input!
            elif event.type == pygame.JOYAXISMOTION:
                if event.dict['axis'] == 1 and event.dict['value'] < 0:
                    changeSelection("up")
                elif event.dict['axis'] == 1 and event.dict['value'] > 0:
                    changeSelection("down")
                elif event.dict['axis'] == 0 and event.dict['value'] < 0:
                    changeSelection("up", True)
                elif event.dict['axis'] == 0 and event.dict['value'] > 0:
                    changeSelection("down", True)

            # Joystick button input!
            elif event.type == pygame.JOYBUTTONDOWN:
                if event.button == 4:
                    changeSelection("up", True)
                elif event.button == 5:
                    changeSelection("down", True)
                elif event.button == 6:
                    changeSelection("down")
                elif event.button == 0 or event.button == 7:
                    print("Loading: " + romList[currentPage * settings['roms_per_page'] + currentSelection]['title'])
                    pygame.quit()
                    time.sleep(1)
                    os.system(settings['emulator_path'] + ' "' + romList[currentPage * settings['roms_per_page'] + currentSelection]['fullPath'] + '"')
                    exit()
                elif event.button == 1:
                    romListOpen = False
                    currentSelection = 0

# Define the initialization function, which will set up the program.
def initialize():

    # Before we do a single thing, free up some memory (non-destructively) so that we don't crash while loading.
    #print("Clearing up memory...")
    #os.system('sync && echo 3 > /proc/sys/vm/drop_caches')

    # Initialize the pygame library.
    print("Launching!")
    pygame.init()
    
    # Shut down the audio mixer immediately to reduce white noise on the analog audio output of the Pi.
    pygame.mixer.quit()

    # Initialize the joysticks.
    for joystick in range(pygame.joystick.get_count()):
        pygame.joystick.Joystick(joystick).init()

    # Grab the list of program options and colors from the parsed configuration file.
    settings = userSettings['options']
    colors = userSettings['colors']
    
    # Set up the display.
    if settings['fullscreen']:
        screen = pygame.display.set_mode([settings['screen_width'], settings['screen_height']], pygame.FULLSCREEN)
    else:
        screen = pygame.display.set_mode([settings['screen_width'], settings['screen_height']])
        pygame.display.set_caption('SNeezy')
        pygame.mouse.set_visible(False)

    # Before loading any other stuff, load the loading screen image and resize it to fit the screen.
    resources['loading_screen'] = scaleToFit(pygame.image.load('resources/images/loading.png').convert_alpha(), screen.get_height())

    # Draw the loading screen.
    drawStatusScreen(screen, "load")
    pygame.display.flip()

    # Load the font and image files needed into the resource table.
    resources['font'] = pygame.font.Font('resources/fonts/' + settings['font_file'], settings['font_size'])
    resources['logo'] = scaleToFit(pygame.image.load('resources/images/logo.png').convert_alpha(), screen.get_height() * settings['header_height'])
    resources['play_icon'] = scaleToFit(pygame.image.load('resources/images/play.png').convert_alpha(), (screen.get_width() * settings['icon_size']), False)
    resources['cartridge_icon'] = scaleToFit(pygame.image.load('resources/images/cartridge.png').convert_alpha(), (screen.get_width() * settings['icon_size']), False)
    resources['volume_icon'] = scaleToFit(pygame.image.load('resources/images/volume.png').convert_alpha(), (screen.get_width() * settings['icon_size']), False)
    resources['reboot_icon'] = scaleToFit(pygame.image.load('resources/images/reboot.png').convert_alpha(), (screen.get_width() * settings['icon_size']), False)
    resources['shutdown_icon'] = scaleToFit(pygame.image.load('resources/images/shutdown.png').convert_alpha(), (screen.get_width() * settings['icon_size']), False)
    resources['loading_boxart'] = scaleToFit(pygame.image.load('resources/images/loading_boxart.png').convert_alpha(), (screen.get_width() * settings['icon_size']), False)
    resources['rebooting_screen'] = scaleToFit(pygame.image.load('resources/images/rebooting.png').convert_alpha(), screen.get_height())
    resources['shutting_down_screen'] = scaleToFit(pygame.image.load('resources/images/shutting_down.png').convert_alpha(), screen.get_height())

    # Prepare to handle the global romList and numberOfPages variables.
    global romList, numberOfPages

    # Populate the ROM list with all of the files in the ROM directory.
    supportedExtensions = [".sfc", ".smc", ".fig"]
    for romFile in os.listdir(settings['rom_folder']):
        romPath = os.path.join(os.getcwd(), settings['rom_folder'], romFile)
        if os.path.isfile(romPath):
            romList.append({'title': romFile,
                            'fullPath': romPath,
                            'boxartPath': 'resources/images/missing_boxart.png',
                            'boxartImage': resources['loading_boxart'],
                            'boxartLoaded': False})

    # Remove the file extensions from the title of each ROM.
    for listItem in romList:
        for extension in supportedExtensions:
            listItem['title'] = listItem['title'].replace(extension, "")

    # Try to find boxart for each ROM.
    for listItem in romList:
        boxartPath = os.path.join(settings['boxart_folder'], listItem['title'] + ".png")
        if os.path.isfile(boxartPath):
            listItem['boxartPath'] = boxartPath

    # If it's been specified, load all of the ROM images here instead of later.
    if not settings['threaded_boxart_loader'] and settings['load_boxart']:
        for listItem in romList:
            listItem['boxartImage'] = scaleToFit(pygame.image.load(listItem['boxartPath']).convert_alpha(), (screen.get_width() * settings['icon_size']), False)
            listItem['boxartLoaded'] = True

    # If it's been specified to do so in the configuration file, sort the ROMs.
    if settings['sort_roms']:
        romList = sorted(romList, key=lambda rom: rom['title'])

    # Calculate the number of pages of ROMs for the ROM list screen.
    numberOfPages = int(math.ceil(len(romList) / float(settings['roms_per_page'])))
    
    # Start a timer to update the temperature reading every second and then update the temperature for the first time.
    pygame.time.set_timer(pygame.USEREVENT + 1, 1000)
    updateTemperature()
    
    # Set the volume level.
    setVolume(volumeLevel)

    # Set up the environment and enter the main loop.
    timer = pygame.time.Clock()
    running = True
    while running:

        # Run at the framerate specified by the user.
        timer.tick(settings['max_fps'])

        # If the QUIT event was issued, exit the loop.
        if pygame.event.get(pygame.QUIT):
            running = False
            return

        # Handle any input events.
        handleInput(pygame.event.get(), screen)

        # If the ROM list is not open, draw the menu. Otherwise, draw the ROM list.
        if not romListOpen:
            drawMenu(screen)
        else:
            drawRomList(screen)

        # Flip the buffers on the display.
        pygame.display.flip()

# Run the program.
initialize()
