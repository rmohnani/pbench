from abc import ABC, abstractmethod
import os
import time

class PbenchCombinedData:
    def __init__(self, diagnostic_checks):
        self.data = dict()
        self.diagnostics = {"run" : dict(), "result": dict()}
        self.diagnostic_checks = diagnostic_checks
    
    def add_run_data(self, doc):
        run_diagnostic = self.diagnostics["run"]

        run = doc["_source"]
        run_id = run["@metadata"]["md5"]

        invalid = False
        # create run_diagnostic data for all checks
        for check in self.diagnostic_checks["run"]:
            diagnostic_update, issue = check.run_diagnostic(doc)
            run_diagnostic.update(diagnostic_update)
            invalid |= issue

        run_diagnostic["valid"] = not invalid
        # update record valid status
        if run_diagnostic["valid"] == True:
            run_index = doc["_index"]

            # TODO: Figure out what exactly this sosreport section is doing,
            #       cuz I still don't know
            sosreports = dict()
            # FIXME: Should I remove the forloop here after the above change?
            for sosreport in run["sosreports"]:
                sosreports[os.path.split(sosreport["name"])[1]] = {
                    "hostname-s": sosreport["hostname-s"],
                    "hostname-f": sosreport["hostname-f"],
                    "time": sosreport["name"].split("/")[2],
                    "inet": [nic["ipaddr"] for nic in sosreport["inet"]],
                    # FIXME: Key Error on inet6
                    # "inet6": [nic["ipaddr"] for nic in sosreport["inet6"]],
                }

            self.data.update({
                "run_id": run_id,
                "run_index": run_index,
                "controller_dir": run["@metadata"]["controller_dir"],
                "sosreports": sosreports,
                "diagnostics": self.diagnostics
            })
    

class PbenchCombinedDataCollection:
    def __init__(self):
        self.run_id_to_data = dict()
        self.trackers = {"run": dict(), "result": dict()}
        self.diagnostic_checks = {"run": [ControllerDirCheck, SosreportCheck],
                                    "result": []}
        self.trackers_initialization()

    
    def trackers_initialization(self):
        for type in self.diagnostic_checks:
            self.trackers[type]["valid"] = 0
            self.trackers[type]["total_records"] = 0
            for check in self.diagnostic_checks[type]:
                check_instance = check()
                for name in check_instance.diagnostic_names:
                    self.trackers[type].update({name: 0})

    def update_run_diagnostic_trackers(self, record : PbenchCombinedData):
        run_diagnostic = record.data["diagnostics"]["run"]
        # update trackers based on run_diagnostic data collected
        self.trackers["run"]['total_records'] += 1
        for diagnostic in run_diagnostic:
            if run_diagnostic[diagnostic] == True:
                self.trackers["run"][diagnostic] += 1
        
    def print_stats(self):
        stats = "Pbench runs Stats: \n"
        for tracker in self.trackers:
            stats += f"{tracker}: {self.trackers[tracker] : n} \n"

        print(stats, flush=True)
    
    def add_run(self, doc):
        new_run = PbenchCombinedData(self.diagnostic_checks)
        new_run.add_run_data(doc)
        time.sleep(1)
        print(new_run.data)
        self.update_run_diagnostic_trackers(new_run)
        run_id = new_run.data["run_id"]
        self.run_id_to_data[run_id] = new_run

    
    def get_runs(self):
        return self.run_id_to_data

 
class DiagnosticCheck(ABC):
 
    # needs to return dictionary of form: 
    # {'diagonstic_name' : diagnostic_val}
    @staticmethod
    @abstractmethod
    def run_diagnostic(doc):
        ...
    
    @property
    @abstractmethod
    def diagnostic_names(self):
        ...

class ControllerDirCheck(DiagnosticCheck):

    def run_diagnostic(doc):
        issues = False
        diagnostic_return = {"missing_ctrl_dir": False}
        if "controller_dir" not in doc["_source"]["@metadata"]:
            diagnostic_return["missing_ctrl_dir"] = True
            issues = True
        return diagnostic_return, issues
    
    @property
    def diagnostic_names(self):
        return ["missing_ctrl_dir"]

    

class SosreportCheck(DiagnosticCheck):

    def run_diagnostic(doc):
        diagnostic_return = dict()
        diagnostic_return["missing_sosreports"] = False
        diagnostic_return["non_2_sosreports"] = False
        diagnostic_return["sosreports_diff_hosts"] = False
        issues = True
        
        # check if sosreports present
        if "sosreports" not in doc["_source"]:
            diagnostic_return["missing_sosreports"] = True
            return diagnostic_return, issues
        
        # check if run has exactly 2 sosreports
        if len(doc["_source"]["sosreports"]) != 2:
            diagnostic_return["non_2_sosreports"] = True
            return diagnostic_return, issues
        
        # check if 2 sosreports have different hosts
        first = doc["_source"]["sosreports"][0]
        second = doc["_source"]["sosreports"][1]
        if first["hostname-f"] != second["hostname-f"]:
            diagnostic_return["sosreports_diff_hosts"] = True
            return diagnostic_return, issues
        
        issues = False
        return diagnostic_return, issues
    
    @property
    def diagnostic_names(self):
        return ["missing_sosreports", "non_2_sosreports", "sosreports_diff_hosts"]
