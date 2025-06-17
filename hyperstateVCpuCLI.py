import numpy as np
from typing import List, Dict
import time
import cmd
import itertools
from math import exp

class Node:
    def __init__(self, node_id: int, num_states: int = 4):
        self.node_id = node_id
        self.num_states = num_states
        self.hyperstate = np.ones(num_states) / num_states
        self.neighbors = []
        self.couplings = {}
        self.local_field = np.random.uniform(-0.5, 0.5, num_states)  # Reduced randomness

    def set_neighbors(self, neighbors: List[int], coupling_strength: float = 1.0):
        self.neighbors = neighbors
        for neighbor_id in neighbors:
            self.couplings[neighbor_id] = np.random.uniform(0.5, coupling_strength) if coupling_strength > 0 else np.random.uniform(-coupling_strength, coupling_strength)

    def apply_local_operation(self, nodes: Dict[int, 'Node'], temperature: float, task: str = 'ising'):
        energies = np.zeros(self.num_states)
        for state in range(self.num_states):
            if task == 'ising':
                energies[state] = self.local_field[state]
                for neighbor_id in self.neighbors:
                    neighbor_state = np.argmax(nodes[neighbor_id].hyperstate)
                    energies[state] += self.couplings[neighbor_id] * (state - 2) * (neighbor_state - 2)
            elif task == 'maxcut':
                for neighbor_id in self.neighbors:
                    neighbor_state = np.argmax(nodes[neighbor_id].hyperstate)
                    energies[state] -= self.couplings[neighbor_id] if state != neighbor_state else 0
        energies = -energies / temperature
        exp_energies = np.exp(energies - np.max(energies))
        self.hyperstate = exp_energies / exp_energies.sum()

    def communicate(self, nodes: Dict[int, 'Node'], task: str = 'ising'):
        interaction = np.zeros(self.num_states)
        for neighbor_id in self.neighbors:
            coupling = self.couplings[neighbor_id]
            interaction += coupling * nodes[neighbor_id].hyperstate
        strength = 0.2 if task == 'ising' else 0.3
        self.hyperstate = (1 - strength) * self.hyperstate + strength * interaction
        self.hyperstate = np.maximum(self.hyperstate, 0)
        self.hyperstate /= self.hyperstate.sum()

    def evaluate(self, nodes: Dict[int, 'Node'], task: str = 'ising') -> float:
        state_idx = np.argmax(self.hyperstate)
        if task == 'ising':
            energy = self.local_field[state_idx]
            for neighbor_id in self.neighbors:
                neighbor_state = np.argmax(nodes[neighbor_id].hyperstate)
                energy += self.couplings[neighbor_id] * (state_idx - 2) * (neighbor_state - 2)
            return energy
        elif task == 'maxcut':
            cut_value = 0
            for neighbor_id in self.neighbors:
                neighbor_state = np.argmax(nodes[neighbor_id].hyperstate)
                if state_idx != neighbor_state:
                    cut_value += self.couplings[neighbor_id]
            return -cut_value

class HyperstateLayer:
    def __init__(self, num_nodes: int, num_states: int = 4):
        self.num_nodes = num_nodes
        self.num_states = num_states
        self.nodes = {i: Node(i, num_states) for i in range(num_nodes)}
        self.topology = 'fully_connected'
        self.set_topology()

    def set_topology(self, topology: str = 'fully_connected'):
        self.topology = topology
        for i in range(self.num_nodes):
            if topology == 'fully_connected':
                neighbors = [j for j in range(self.num_nodes) if j != i]
            elif topology == 'ring':
                neighbors = [(i - 1) % self.num_nodes, (i + 1) % self.num_nodes]
            else:
                raise ValueError("Unsupported topology")
            coupling_strength = 1.0 if self.topology == 'maxcut' else -1.0
            self.nodes[i].set_neighbors(neighbors, coupling_strength=coupling_strength)

    def step(self, temperature: float, task: str = 'ising'):
        for node in self.nodes.values():
            node.apply_local_operation(self.nodes, temperature, task)
        for node in self.nodes.values():
            node.communicate(self.nodes, task)

    def optimize(self, iterations: int, initial_temperature: float = 0.5, task: str = 'ising') -> float:
        for i in range(iterations):
            if task == 'ising':
                temperature = initial_temperature * exp(-0.01 * i) + 0.01  # Exponential annealing
            else:
                temperature = initial_temperature / (1 + 0.05 * i) + 0.01  # Logarithmic for MAX-CUT
            self.step(temperature, task)
        return sum(node.evaluate(self.nodes, task) for node in self.nodes.values())

def classical_exhaustive_search(num_nodes: int, num_states: int = 4, task: str = 'ising') -> tuple[float, int]:
    min_energy = float('inf')
    iterations = 0
    for config in itertools.product(range(num_states), repeat=num_nodes):
        iterations += 1
        nodes = {i: Node(i, num_states) for i in range(num_nodes)}
        for i in range(num_nodes):
            nodes[i].set_neighbors([j for j in range(num_nodes) if j != i])
            nodes[i].hyperstate = np.zeros(num_states)
            nodes[i].hyperstate[config[i]] = 1.0
        energy = sum(nodes[i].evaluate(nodes, task) for i in nodes)
        min_energy = min(min_energy, energy)
    return min_energy, iterations

def classical_hill_climbing(num_nodes: int, num_states: int = 4, max_iterations: int = 1000, task: str = 'ising') -> tuple[float, int]:
    nodes = {i: Node(i, num_states) for i in range(num_nodes)}
    for i in range(num_nodes):
        nodes[i].set_neighbors([j for j in range(num_nodes) if j != i])
        nodes[i].hyperstate = np.random.random(num_states)
        nodes[i].hyperstate /= nodes[i].hyperstate.sum()
    current_energy = sum(nodes[i].evaluate(nodes, task) for i in nodes)
    iterations = 0
    for _ in range(max_iterations):
        iterations += 1
        node_id = np.random.randint(num_nodes)
        old_hyperstate = nodes[node_id].hyperstate.copy()
        nodes[node_id].hyperstate = np.random.random(num_states)
        nodes[node_id].hyperstate /= nodes[node_id].hyperstate.sum()
        new_energy = sum(nodes[i].evaluate(nodes, task) for i in nodes)
        if new_energy >= current_energy:
            nodes[node_id].hyperstate = old_hyperstate
        else:
            current_energy = new_energy
    return current_energy, iterations

class HyperstateCLI(cmd.Cmd):
    intro = "Hyperstate vCPU Simulator. Type 'help' for commands or 'quit' to exit."
    prompt = "(HyperstateVCpu) "

    def __init__(self):
        super().__init__()
        self.layer = None

    def do_init(self, arg):
        """Initialize layer: init <num_nodes> <num_states>"""
        try:
            num_nodes, num_states = map(int, arg.split())
            self.layer = HyperstateLayer(num_nodes=num_nodes, num_states=num_states)
            print(f"Initialized layer with {num_nodes} nodes and {num_states} states")
        except ValueError:
            print("Usage: init <num_nodes> <num_states>")

    def do_set_topology(self, arg):
        """Set graph topology: set_topology <fully_connected|ring>"""
        if not self.layer:
            print("Layer not initialized. Use 'init' first.")
            return
        try:
            self.layer.set_topology(arg)
            print(f"Set topology to {arg}")
        except ValueError as e:
            print(str(e))

    def do_optimize(self, arg):
        """Run optimization: optimize <iterations> [<initial_temperature>] [<task>]"""
        if not self.layer:
            print("Layer not initialized. Use 'init' first.")
            return
        try:
            args = arg.split()
            iterations = int(args[0])
            initial_temperature = float(args[1]) if len(args) > 1 else 0.5
            task = args[2] if len(args) > 2 else 'ising'
            if task not in ['ising', 'maxcut']:
                raise ValueError("Task must be 'ising' or 'maxcut'")
            start_time = time.time()
            initial_energy = self.layer.optimize(0, initial_temperature, task)
            final_energy = self.layer.optimize(iterations, initial_temperature, task)
            print(f"Initial {'energy' if task == 'ising' else 'cut value'}: {initial_energy:.4f}")
            print(f"Final {'energy' if task == 'ising' else 'cut value'} after {iterations} iterations: {final_energy:.4f}")
            print(f"Time: {time.time() - start_time:.6f} seconds")
        except (ValueError, IndexError):
            print("Usage: optimize <iterations> [<initial_temperature>] [<task>]")

    def do_benchmark(self, arg):
        """Run benchmark: benchmark <task>"""
        if not self.layer:
            print("Layer not initialized. Use 'init' first.")
            return
        task = arg if arg in ['ising', 'maxcut'] else 'ising'
        print(f"\nBenchmark: {task.upper()} problem with {self.layer.num_nodes} nodes")
        # Hyperstate layer
        start_time = time.time()
        initial_energy = self.layer.optimize(0, 0.5, task)
        final_energy = self.layer.optimize(300, 0.5, task)  # Increased to 300 iterations
        hyperstate_time = time.time() - start_time
        classical_energy, _ = classical_exhaustive_search(self.layer.num_nodes, self.layer.num_states, task)
        print(f"Hyperstate layer - Initial {'energy' if task == 'ising' else 'cut value'}: {initial_energy:.4f}")
        print(f"Hyperstate layer - Final {'energy' if task == 'ising' else 'cut value'} after 300 iterations: {final_energy:.4f}, Time: {hyperstate_time:.6f} seconds")
        if final_energy != 0:
            print(f"Percentage of optimal {'energy' if task == 'ising' else 'cut'} (based on exhaustive): {(final_energy / classical_energy) * 100:.2f}%")
        # Classical exhaustive search
        start_time = time.time()
        classical_energy, classical_iterations = classical_exhaustive_search(self.layer.num_nodes, self.layer.num_states, task)
        classical_time = time.time() - start_time
        print(f"Classical exhaustive search - {'Energy' if task == 'ising' else 'Cut value'}: {classical_energy:.4f}, Iterations: {classical_iterations}, Time: {classical_time:.6f} seconds")
        print(f"Advantage (iterations, exhaustive): {classical_iterations / 300:.2f}x")
        # Classical hill climbing
        start_time = time.time()
        hill_energy, hill_iterations = classical_hill_climbing(self.layer.num_nodes, self.layer.num_states, max_iterations=1000, task=task)
        hill_time = time.time() - start_time
        print(f"Classical hill climbing - {'Energy' if task == 'ising' else 'Cut value'}: {hill_energy:.4f}, Iterations: {hill_iterations}, Time: {hill_time:.6f} seconds")
        print(f"Advantage (iterations, hill climbing): {hill_iterations / 300:.2f}x")
        if hill_energy != 0:
            print(f"Percentage of optimal {'energy' if task == 'ising' else 'cut'} (hill climbing): {(hill_energy / classical_energy) * 100:.2f}%")

    def do_quit(self, arg):
        """Exit the simulator"""
        print("Exiting HyperstateVCpu")
        return True

if __name__ == "__main__":
    np.random.seed(42)
    HyperstateCLI().cmdloop()