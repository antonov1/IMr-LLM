def parse_constraints(file_path):
    constraints_dict = {
        'atmost1': [],
        'existence': [],
        'response': [],
        'precedence': [],
        'coexistence': [],
        'noncoexistence': [],
        'nonsuccession': [],
        'responded_existence': []
    }

    with open(file_path, 'r') as file:
        lines = file.readlines()

        for line in lines:
            line = line.strip()
            if line.startswith('AtMost1'):
                activity = line[len('AtMost1('):-1].strip()
                constraints_dict['atmost1'].append((activity,))
            elif line.startswith('Existence'):
                activity = line[len('Existence('):-1].strip()
                constraints_dict['existence'].append((activity,))
            elif line.startswith('Response'):
                activities = line[len('Response('):-1].split(',')
                activities = tuple(activity.strip() for activity in activities)
                constraints_dict['response'].append(activities)
            elif line.startswith('Precedence'):
                activities = line[len('Precedence('):-1].split(',')
                activities = tuple(activity.strip() for activity in activities)
                constraints_dict['precedence'].append(activities)
            elif line.startswith('CoExistence'):
                activities = line[len('CoExistence('):-1].split(',')
                activities = tuple(activity.strip() for activity in activities)
                constraints_dict['coexistence'].append(activities)
            elif line.startswith('NotCoExistence'):
                activities = line[len('NotCoExistence('):-1].split(',')
                activities = tuple(activity.strip() for activity in activities)
                constraints_dict['noncoexistence'].append(activities)
            elif line.startswith('NotSuccession'):
                activities = line[len('NotSuccession('):-1].split(',')
                activities = tuple(activity.strip() for activity in activities)
                constraints_dict['nonsuccession'].append(activities)
            elif line.startswith('RespondedExistence'):
                activities = line[len('RespondedExistence('):-1].split(',')
                activities = tuple(activity.strip() for activity in activities)
                constraints_dict['responded_existence'].append(activities)
            elif line.startswith('ChainResponse'):
                raise ValueError("Unsupported Rule")
            elif line.startswith('ChainPrecedence'):
                raise ValueError("Unsupported Rule")


    return constraints_dict


