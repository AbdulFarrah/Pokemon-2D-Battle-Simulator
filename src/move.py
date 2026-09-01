class Move:
    def __init__(self, json_data):
        self.name = json_data['Name']
        self.type = json_data['Type']
        self.category = json_data['Category']
        # TODO: deal with contest type later
        self.contest = json_data['Contest']
        self.pp = int(json_data['PP'])
        self.max_pp = int(json_data['PP'])
        if json_data['Power'] != 'None':
            self.power = int(json_data['Power'])
        else:
            self.power = json_data['Power']
        
        if json_data['Accuracy'] != 'None':
            self.accuracy = int(json_data['Accuracy'])
        else:
            self.accuracy = json_data['Accuracy']

    def update_pp(self, delta):
        self.pp += delta