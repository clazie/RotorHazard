''' Heat generator for ladders '''

import logging
import RHUtils
import random
from HeatGenerator import HeatGenerator
from Database import ProgramMethod
from RHUI import UIField, UIFieldType, UIFieldSelectOption

logger = logging.getLogger(__name__)

def registerHandlers(args):
    if 'registerFn' in args:
        for generator in discover():
            args['registerFn'](generator)

def __(arg): # Replaced with outer language.__ during initialize()
    return arg

def initialize(**kwargs):
    if 'Events' in kwargs:
        kwargs['Events'].on('HeatGenerator_Initialize', 'HeatGenerator_register_ladder', registerHandlers, {}, 75)
    if '__' in kwargs:
        __ = kwargs['__']

def getTotalPilots(RHAPI, generate_args):
    input_class_id = generate_args.get('input_class')

    if input_class_id:
        if 'total_pilots' in generate_args:
            total_pilots = int(generate_args['total_pilots'])
        else:
            race_class = RHAPI.db.raceclass_by_id(input_class_id)
            class_results = RHAPI.db.raceclass_results(race_class)
            if class_results and type(class_results) == dict:
                # fill from available results
                total_pilots = len(class_results['by_race_time'])
            else:
                # fall back to all pilots
                total_pilots = len(RHAPI.db.pilots)
    else:
        # use total number of pilots
        total_pilots = len(RHAPI.db.pilots)

    return total_pilots

def generateLadder(RHAPI, generate_args=None):
    available_nodes = generate_args.get('available_nodes')
    suffix = __(generate_args.get('suffix', 'Main'))

    if 'qualifiers_per_heat' in generate_args and 'advances_per_heat' in generate_args:
        qualifiers_per_heat = int(generate_args['qualifiers_per_heat'])
        advances_per_heat = int(generate_args['advances_per_heat'])
    elif 'advances_per_heat' in generate_args:
        advances_per_heat = int(generate_args['advances_per_heat'])
        qualifiers_per_heat = available_nodes - advances_per_heat
    elif 'qualifiers_per_heat' in generate_args:
        qualifiers_per_heat = int(generate_args['qualifiers_per_heat'])
        advances_per_heat = available_nodes - qualifiers_per_heat
    else:
        qualifiers_per_heat = available_nodes - 1
        advances_per_heat = 1

    if qualifiers_per_heat < 1 or advances_per_heat < 1:
        if not ('advances_per_heat' in generate_args and generate_args['advances_per_heat'] == 0):
            logger.warning('Unable to seed ladder: provided qualifiers and advances must be > 0')
            return False

    total_pilots = getTotalPilots(RHAPI, generate_args)

    if total_pilots == 0:
        logger.warning('Unable to seed ladder: no pilots available')
        return False

    letters = __('ABCDEFGHIJKLMNOPQRSTUVWXYZ')
    heats = []

    if 'seed_offset' in generate_args:
        seed_offset = max(int(generate_args['seed_offset']) - 1, 0)
    else:
        seed_offset = 0

    unseeded_pilots = list(range(seed_offset, total_pilots+seed_offset))
    heat_pilots = 0

    while len(unseeded_pilots):
        if heat_pilots == 0:
            heat = {
                'name': letters[len(heats)] + ' ' + suffix,
                'slots': []
                }

        if heat_pilots < qualifiers_per_heat:
            # slot qualifiers
            heat['slots'].append({
                    'method': 'input',
                    'seed_rank': unseeded_pilots.pop(0) + 1
                })

            heat_pilots += 1
        else:
            if len(unseeded_pilots) <= advances_per_heat:
                # slot remainder as qualifiers
                for seed in unseeded_pilots:
                    heat['slots'].append({
                            'method': 'input',
                            'seed_rank': seed + 1
                        })

                unseeded_pilots = [] # empty after using

            else:
                # slot advances
                for adv_idx in range(advances_per_heat):
                    heat['slots'].append({
                            'method': ProgramMethod.HEAT_RESULT,
                            'seed_heat_id': -len(heats) - 2,
                            'seed_rank': adv_idx + 1,
                        })

            heats = [heat, *heats] # insert at front
            heat_pilots = 0

    if heat_pilots: # insert final heat
        heats = [heat, *heats]

    return heats

def generateBalancedHeats(RHAPI, generate_args=None):
    available_nodes = generate_args.get('available_nodes')
    suffix = __(generate_args.get('suffix', 'Qualifier'))

    if 'qualifiers_per_heat' in generate_args:
        qualifiers_per_heat = generate_args['qualifiers_per_heat']
    else:
        qualifiers_per_heat = available_nodes

    if qualifiers_per_heat < 1:
        logger.warning('Unable to seed ladder: provided qualifiers must be > 1')
        return False

    total_pilots = getTotalPilots(RHAPI, generate_args)

    if total_pilots == 0:
        logger.warning('Unable to seed heats: no pilots available')
        return False

    total_heats = (total_pilots // qualifiers_per_heat)
    if total_pilots % qualifiers_per_heat:
        total_heats += 1

    letters = __('ABCDEFGHIJKLMNOPQRSTUVWXYZ')
    heats = []

    for idx in range(total_heats):
        heats.append({
            'name': letters[idx] + ' ' + suffix,
            'slots': []
            })

    if 'seed_offset' in generate_args:
        seed_offset = max(int(generate_args['seed_offset']) - 1, 0)
    else:
        seed_offset = 0

    unseeded_pilots = list(range(seed_offset, total_pilots+seed_offset))
    random.shuffle(unseeded_pilots)

    heatNum = 0
    while len(unseeded_pilots):
        if heatNum >= len(heats):
            heatNum = 0

        heats[heatNum]['slots'].append({
                'method': 'input',
                'seed_rank': unseeded_pilots.pop(0) + 1
                })
        heatNum += 1

    return heats

def discover(*_args, **_kwargs):
    # returns array of exporters with default arguments
    return [
        HeatGenerator(
            'ladder_0a',
            'Ranked fill',
            generateLadder,
            {
                'advances_per_heat': 0,
            },
            [
                UIField('qualifiers_per_heat', "Maximum pilots per heat", UIFieldType.BASIC_INT, placeholder="Auto"),
                UIField('total_pilots', "Maxiumum pilots in class", UIFieldType.BASIC_INT, placeholder="Auto", desc="Used only with input class"),
                UIField('seed_offset', "Seed from rank", UIFieldType.BASIC_INT, value=1),
                UIField('suffix', "Heat title suffix", UIFieldType.TEXT, placeholder="Main", value="Main"),
            ],
        ),
        HeatGenerator(
            'balanced_fill',
            'Balanced random fill',
            generateBalancedHeats,
            None,
            [
                UIField('qualifiers_per_heat', "Maximum pilots per heat", UIFieldType.BASIC_INT, placeholder="Auto"),
                UIField('total_pilots', "Maxiumum pilots in class", UIFieldType.BASIC_INT, placeholder="Auto", desc="Used only with input class"),
                UIField('seed_offset', "Seed from rank", UIFieldType.BASIC_INT, value=1),
                UIField('suffix', "Heat title suffix", UIFieldType.TEXT, placeholder="Qualifier", value="Qualifier"),
            ]
        ),
        HeatGenerator(
            'ladder_params',
            'Ladder',
            generateLadder,
            None,
            [
                UIField('advances_per_heat', "Advances per heat", UIFieldType.BASIC_INT, placeholder="Auto"),
                UIField('qualifiers_per_heat', "Seeded slots per heat", UIFieldType.BASIC_INT, placeholder="Auto"),
                UIField('total_pilots', "Pilots in class", UIFieldType.BASIC_INT, placeholder="Auto", desc="Used only with input class"),
                UIField('seed_offset', "Seed from rank", UIFieldType.BASIC_INT, value=1),
                UIField('suffix', "Heat title suffix", UIFieldType.TEXT, placeholder="Main", value="Main"),
            ]
        ),

    ]
