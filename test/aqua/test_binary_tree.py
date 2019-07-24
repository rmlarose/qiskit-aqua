# -*- coding: utf-8 -*-

# This code is part of Qiskit.
#
# (C) Copyright IBM 2018, 2019.
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

# Imports
import numpy as np
import unittest
from itertools import permutations
# TODO: Change the line below to this line before PR: from test.aqua.common import QiskitAquaTestCase
from common import QiskitAquaTestCase
from qiskit.aqua.components.qsve import BinaryTree
from qiskit import QuantumRegister, QuantumCircuit, execute, BasicAer


class TestBinaryTree(QiskitAquaTestCase):
    """Unit tests for BinaryTree class."""
    @staticmethod
    def final_state(circuit):
        """Returns the final state of the circuit as a numpy.ndarray."""
        # Get the unitary simulator backend
        sim = BasicAer.get_backend("unitary_simulator")

        # Execute the circuit
        job = execute(circuit, sim)

        # Get the final state
        unitary = np.array(job.result().results[0].data.unitary)
        return unitary[:, 0]

    def test_basic(self):
        """Basic checks for a BinaryTree."""
        # Instantiate a BinaryTree
        tree = BinaryTree([1, 1])

        # Simple checks
        self.assertTrue(np.isclose(tree.root, 2.0))
        self.assertEqual(tree.number_leaves, 2)
        self.assertEqual(tree.number_levels, 2)

    def test_example_in_paper(self):
        """Tests correctness for the binary tree in the example given in
        Appendix A of the quantum recommendation systems paper.
        """
        # The same vector used in the paper
        row = [0.4, 0.4, 0.8, 0.2]

        # Construct the tree from the vector
        tree = BinaryTree(row)

        # Make sure the elements are equal
        self.assertTrue(np.isclose(tree.data[0][0], 1.0))
        self.assertTrue(np.isclose(tree.data[1][0], 0.32))
        self.assertTrue(np.isclose(tree.data[1][1], 0.68))
        self.assertTrue(np.isclose(tree.data[2][0], 0.16))
        self.assertTrue(np.isclose(tree.data[2][1], 0.16))
        self.assertTrue(np.isclose(tree.data[2][2], 0.64))
        self.assertTrue(np.isclose(tree.data[2][3], 0.04))

    def test_print_small(self):
        """Tests the correct string format is obtained when printing a small tree."""
        tree = BinaryTree([1, 1])
        correct = "    2.00    \n1.00    1.00\n"
        self.assertEqual(tree.__str__(), correct)

    def test_number_leaves(self):
        """Tests the number of leaves is correct for a BinaryTree."""
        # Create a tree
        tree = BinaryTree(np.ones(128))

        # Make sure the number of leaves is correct
        self.assertEqual(tree.number_leaves, 128)

    def test_number_levels(self):
        """Tests the number of levels is correct for a BinaryTree."""
        # Create a tree
        tree = BinaryTree(np.ones(32))

        # Make sure the number of leaves is correct
        self.assertEqual(tree.number_levels, 6)

    def test_parent_indices(self):
        """Tests correctness for getting parent indices.

        The relevant indexing structure here is:

                         (0, 0)
                           ^
                   (1, 0)     (1, 1)
                     ^          ^
               (2, 0) (2, 1) (2, 2) (2, 3)

        """
        tree = BinaryTree([1, 1, 1, 1])

        # Test that the parent of root is none
        self.assertIsNone(tree.parent_index(0, 0))

        # Test that the parent's of the first level are the root
        self.assertEqual(tree.parent_index(1, 0), (0, 0))
        self.assertEqual(tree.parent_index(1, 1), (0, 0))

        # Test that the parent's of the second level are correct
        self.assertEqual(tree.parent_index(2, 0), (1, 0))
        self.assertEqual(tree.parent_index(2, 1), (1, 0))
        self.assertEqual(tree.parent_index(2, 2), (1, 1))
        self.assertEqual(tree.parent_index(2, 3), (1, 1))

    def test_parent_value(self):
        """Tests correctness for getting the parent value of a node."""
        # Get a BinaryTree
        tree = BinaryTree([1, 1, 1, 1])

        # Make sure the parent of the root is None
        self.assertIsNone(tree.parent_value(0, 0))

        # Make sure the parent's of the first level (root) are correct
        self.assertTrue(np.isclose(tree.parent_value(1, 0), 4.0))
        self.assertTrue(np.isclose(tree.parent_value(1, 1), 4.0))

        # Make sure the parent's of the second level are correct
        self.assertTrue(np.isclose(tree.parent_value(2, 0), 2.0))
        self.assertTrue(np.isclose(tree.parent_value(2, 1), 2.0))
        self.assertTrue(np.isclose(tree.parent_value(2, 2), 2.0))
        self.assertTrue(np.isclose(tree.parent_value(2, 3), 2.0))

    def test_left_child_index(self):
        """Tests getting the index of the left child."""
        # Get a BinaryTree
        tree = BinaryTree([1, 2, 3, 4])

        # Left child of the root
        self.assertEqual(tree.left_child_index(0, 0), (1, 0))

        # Left child indices for the first level
        self.assertEqual(tree.left_child_index(1, 0), (2, 0))
        self.assertEqual(tree.left_child_index(1, 1), (2, 2))

        # Left child indices for leaves
        self.assertIsNone(tree.left_child_index(2, 0))
        self.assertIsNone(tree.left_child_index(2, 1))
        self.assertIsNone(tree.left_child_index(2, 2))
        self.assertIsNone(tree.left_child_index(2, 3))

    def test_right_child_index(self):
        """Tests getting the index of a right child for a set of nodes."""
        # Get a BinaryTree
        tree = BinaryTree([1, 2, 3, 4])

        # Right child of the root
        self.assertEqual(tree.right_child_index(0, 0), (1, 1))

        # Right child indices for the first level
        self.assertEqual(tree.right_child_index(1, 0), (2, 1))
        self.assertEqual(tree.right_child_index(1, 1), (2, 3))

        # Right child indices for leaves
        self.assertIsNone(tree.right_child_index(2, 0))
        self.assertIsNone(tree.right_child_index(2, 1))
        self.assertIsNone(tree.right_child_index(2, 2))
        self.assertIsNone(tree.right_child_index(2, 3))

    def test_left_child_value(self):
        """Tests getting the value of a left child for a set of nodes."""
        # Get a BinaryTree
        tree = BinaryTree([1, 1, 1, 1])

        # Check the root value
        self.assertTrue(np.isclose(tree.root, 4.0))

        # Left child of the root
        self.assertTrue(np.isclose(tree.left_child_value(0, 0), 2.0))

        # Left child indices for the first level
        self.assertTrue(np.isclose(tree.left_child_value(1, 0), 1.0))
        self.assertTrue(np.isclose(tree.left_child_value(1, 1), 1.0))

        # Left child indices for leaves
        self.assertIsNone(tree.left_child_value(2, 0))
        self.assertIsNone(tree.left_child_value(2, 1))
        self.assertIsNone(tree.left_child_value(2, 2))
        self.assertIsNone(tree.left_child_value(2, 3))

    def test_right_child_value(self):
        """Tests getting the value of a right child for a set of nodes."""
        # Get a BinaryTree
        tree = BinaryTree([1, 1, 1, 1])

        # Check root value
        self.assertTrue(np.isclose(tree.root, 4.0))

        # Right child of the root
        self.assertTrue(np.isclose(tree.right_child_value(0, 0), 2.0))

        # Right child indices for the first level
        self.assertTrue(np.isclose(tree.right_child_value(1, 0), 1.0))
        self.assertTrue(np.isclose(tree.right_child_value(1, 1), 1.0))

        # Right child indices for leaves
        self.assertIsNone(tree.right_child_value(2, 0))
        self.assertIsNone(tree.right_child_value(2, 1))
        self.assertIsNone(tree.right_child_value(2, 2))
        self.assertIsNone(tree.right_child_value(2, 3))

    def test_prep_circuit_one_qubit(self):
        """Tests for correctness in preparation circuit on a single qubit."""
        # Two element vector
        vec = [1.0, 0.0]

        # Make a BinaryTree
        tree = BinaryTree(vec)

        # Get the state preparation circuit
        circ = tree.preparation_circuit(QuantumRegister(1))

        # Get the final state
        state = list(np.real(self.final_state(circ)))

        self.assertTrue( np.array_equal(state, vec))

    def test_prep_circuit_one_qubit2(self):
        """Tests for correctness in preparation circuit on a single qubit."""
        # Two element vector
        vec = [0.0, 1.0]

        # Make a BinaryTree
        tree = BinaryTree(vec)

        # Get the state preparation circuit
        circ = tree.preparation_circuit(QuantumRegister(1))

        # Get the final state
        state = list(np.real(self.final_state(circ)))

        self.assertTrue(np.array_equal(state, vec))

    def test_prep_circuit_one_qubit3(self):
        """Tests for correctness in preparation circuit on a single qubit."""
        # Two element vector
        vec = [0.6, 0.8]

        # Make a BinaryTree
        tree = BinaryTree(vec)

        # Get the state preparation circuit
        circ = tree.preparation_circuit(QuantumRegister(1))

        # Get the final state
        state = list(np.real(self.final_state(circ)))

        self.assertTrue(np.array_equal(state, vec))

    def test_prep_circuit_example_in_paper(self):
        """Tests the state preparation circuit produces the correct state
        for the example given in the quantum recommendations system paper.
        """
        # The same vector used in the paper
        vec = [0.4, 0.4, 0.8, 0.2]

        # Construct the tree from the vector
        tree = BinaryTree(vec)

        # Construct the state preparation circuit
        qreg = QuantumRegister(2)
        circuit = tree.preparation_circuit(qreg)

        # Add a swaps to make the ordering of the qubits match the input vector
        # Note: This is because the last bit is the most significant in qiskit, not the first.
        circuit.swap(qreg[0], qreg[1])

        # Check that the circuit produces the correct state
        state = list(np.real(self.final_state(circuit)))
        self.assertTrue(np.allclose(state, vec))

    def test_prep_circuit_three_qubits(self):
        """Tests the state preparation circuit produces the correct state on three qubits."""
        # Input vector
        vec = np.array([1, 2, 3, 4, 5, 6, 7, 8], dtype=np.float64)

        # Make a tree from the vector
        tree = BinaryTree(vec)

        # Get the state preparation circuit
        qreg = QuantumRegister(3)
        circuit = tree.preparation_circuit(qreg)

        # Add a swaps to make the ordering of the qubits match the input vector
        # Note: This is because the last bit is the most significant in qiskit, not the first.
        circuit.swap(qreg[0], qreg[2])

        # Check that the circuit produces the correct state
        state = list(np.real(self.final_state(circuit)))
        self.assertTrue(np.allclose(state, vec / np.linalg.norm(vec, ord=2)))

    def test_prep_circuit_medium(self):
        """Tests the state preparation circuit produces the correct state for a moderate number of qubits."""
        # Input vector
        vec = np.ones(16)

        # Make a tree from the vector
        tree = BinaryTree(vec)

        # Do the state preparation circuit
        circ = tree.preparation_circuit(QuantumRegister(4))

        # Check that the circuit produces the correct state
        # Note: No swaps are necessary here since all amplitudes are equal.
        state = np.real(self.final_state(circ))

        # Note: The output state has an additional ancilla needed to do the multi-controlled-Y rotations,
        # so we discard the additional (zero) amplitudes when comparing to the input vector
        self.assertTrue(np.allclose(state[:16], vec / np.linalg.norm(vec, ord=2)))

    def test_prep_circuit_large(self):
        """Tests the state preparation circuit produces the correct state for many qubits."""
        # Input vector
        vec = np.ones(64)

        # Make a tree from the vector
        tree = BinaryTree(vec)

        # Do the state preparation circuit
        circ = tree.preparation_circuit(QuantumRegister(6))

        # Check that the circuit produces the correct state
        # Note: No swaps are necessary here since all amplitudes are equal.
        state = np.real(self.final_state(circ))

        # Note: The output state has an additional ancilla needed to do the multi-controlled-Y rotations,
        # so we discard the additional (zero) amplitudes when comparing to the input vector
        self.assertTrue(np.allclose(state[:len(vec)], vec / np.linalg.norm(vec, ord=2)))

    def test_prep_circuit_large2(self):
        """Tests the state preparation circuit produces the correct state for many qubits."""
        # Input vector (normalized)
        vec = np.array(list(np.ones(32)) + list(np.zeros(32)))

        # Make a tree from the vector
        tree = BinaryTree(vec)

        # Do the state preparation circuit
        qreg = QuantumRegister(6)
        circ = tree.preparation_circuit(qreg)

        # Do the swaps to get the ordering of amplitudes to match with the input vector
        for ii in range(len(qreg) // 2):
            circ.swap(qreg[ii], qreg[-ii - 1])

        # Check that the circuit produces the correct state
        state = np.real(self.final_state(circ))

        # Note: The output state has an additional ancilla needed to do the multi-controlled-Y rotations,
        # so we discard the additional (zero) amplitudes when comparing to the input vector
        self.assertTrue(np.allclose(state[:len(vec)], vec / np.linalg.norm(vec, ord=2)))

    def test_prepare_negative_amplitudes(self):
        """Tests preparing a vector with negative amplitudes on a single qubit."""
        # Input vector
        vec = [0.6, -0.8]

        # Get a BinaryTree
        tree = BinaryTree(vec)

        # Get the state preparation circuit
        circuit = tree.preparation_circuit(QuantumRegister(1))

        # Make sure the final state of the circuit is the same as the input vector
        state = np.real(self.final_state(circuit))
        self.assertTrue(np.allclose(state, vec))

    def test_prepare_negative_amplitudes2(self):
        """Tests preparing a vector with negative amplitudes on a single qubit."""
        # Input vector
        vec = [-0.6, 0.8]

        # Get a BinaryTree
        tree = BinaryTree(vec)

        # Get the state preparation circuit
        circuit = tree.preparation_circuit(QuantumRegister(1))

        # Make sure the final state of the circuit is the same as the input vector
        state = np.real(self.final_state(circuit))
        self.assertTrue(np.allclose(state, vec))

    def test_prepare_negative_amplitudes3(self):
        """Tests preparing a vector with negative amplitudes on a single qubit."""
        # Input vector
        vec = [-0.6, -0.8]

        # Get a BinaryTree
        tree = BinaryTree(vec)

        # Get the state preparation circuit
        circuit = tree.preparation_circuit(QuantumRegister(1))

        # Make sure the final state of the circuit is the same as the input vector
        state = np.real(self.final_state(circuit))
        self.assertTrue(np.allclose(state, vec))

    def test_prepare_negative_amplitudes_two_qubits(self):
        """Tests preparing a vector with negative amplitudes for the example from
        the quantum recommendations systems paper.
        """
        # Input vector
        vec = [-0.4, 0.4, -0.8, 0.2]

        # Get a BinaryTree
        tree = BinaryTree(vec)

        # Get a Quantum Register
        qreg = QuantumRegister(2)

        # Get the state preparation circuit
        circuit = tree.preparation_circuit(qreg)

        # Swap the qubits to compare to the natural ordering of the vector
        circuit.swap(qreg[0], qreg[1])

        # Make sure the final state of the circuit is the same as the input vector
        state = np.real(self.final_state(circuit))
        self.assertTrue(np.allclose(state, vec))

    def test_prepare_negative_amplitudes_two_qubits2(self):
        """Tests preparing a vector with negative amplitudes on a single qubit."""
        # Generate all sign configurations
        one_neg = set(permutations((-1, 1, 1, 1)))
        two_neg = set(permutations((-1, -1, 1, 1)))
        three_neg = set(permutations((-1, -1, -1, 1)))
        four_neg = {(-1, -1, -1, -1)}

        for sign in one_neg | two_neg | three_neg | four_neg:
            # Input vector
            vec = np.array([1, 2, 3, 4], dtype=np.float64)
            vec *= np.array(sign, dtype=np.float64)

            # Get a BinaryTree
            tree = BinaryTree(vec)

            # Get a quantum register
            qreg = QuantumRegister(2)

            # Get the state preparation circuit
            circuit = tree.preparation_circuit(qreg)

            # Swap qubits to compare with natural ordering of vector
            circuit.swap(qreg[0], qreg[1])

            # Make sure the final state is the same as the input vector
            state = np.real(self.final_state(circuit))
            self.assertTrue(np.allclose(state, vec / np.linalg.norm(vec, ord=2)))

    def test_prepare_negative_amplitudes_three_qubits(self):
        """Tests state preparation for a vector on three qubits with negative amplitudes."""
        # Input vector
        vec = np.array([-1, -2, 3, -4, -5, 6, -7, 8], dtype=np.float64)

        # Get the BinaryTree
        tree = BinaryTree(vec)

        # Quantum register
        qreg = QuantumRegister(3)

        # Get the state preparation circuit
        circuit = tree.preparation_circuit(qreg)

        # Add swaps to compare amplitudes with normal vector ordering
        circuit.swap(qreg[0], qreg[2])

        # Make sure the final state is equal to the input vector
        state = np.real(self.final_state(circuit))
        self.assertTrue(np.allclose(state, vec / np.linalg.norm(vec, ord=2)))

    def test_prepare_negative_amplitudes_four_qubits(self):
        """Tests state preparation for a vector on three qubits with negative amplitudes."""
        # Input vector
        vec = np.array([-1, -2, 3, -4, -5, 6, -7, 8, 9, 10, 11, -12, -13, -14, 15, -16], dtype=np.float64)

        # Get the BinaryTree
        tree = BinaryTree(vec)

        # Quantum register for input
        qreg = QuantumRegister(4)

        # Create the state preparation circuit
        circuit = tree.preparation_circuit(qreg)

        # Add swaps to compare with normal vector ordering
        circuit.swap(qreg[0], qreg[3])
        circuit.swap(qreg[1], qreg[2])

        # Get the final state of the circuit
        state = np.real(self.final_state(circuit))

        # Only compare the first 16 amplitudes (ancillae are needed to do multi-controlled gates)
        self.assertTrue(np.allclose(state[:len(vec)], vec / np.linalg.norm(vec, ord=2)))

    def test_prep_circuit_negative_amplitudes_large(self):
        """Tests the state preparation circuit produces the correct state for many qubits."""
        # Input vector
        vec = -1.0 * np.ones(64)

        # Make a tree from the vector
        tree = BinaryTree(vec)

        # Do the state preparation circuit
        circ = tree.preparation_circuit(QuantumRegister(6))

        # Check that the circuit produces the correct state
        # Note: No swaps are necessary here since all amplitudes are equal.
        state = np.real(self.final_state(circ))

        # Note: The output state has an additional ancilla needed to do the multi-controlled-Y rotations,
        # so we discard the additional (zero) amplitudes when comparing to the input vector
        self.assertTrue( np.allclose(state[:len(vec)], vec / np.linalg.norm(vec, ord=2)))

    def test_prep_circuit_with_control(self):
        """Basic test for the state preparation circuit with a control register.

        This test makes sure the state is created when the control key is 1 and *not* created otherwise.
        """
        # Input vector
        vec = np.ones(2, dtype=np.float64)

        # Zero state
        zero = np.array([1, 0], dtype=np.float64)

        # Make a tree from the vector
        tree = BinaryTree(vec)

        # Registers
        register = QuantumRegister(1)
        control_register = QuantumRegister(1)

        # Do controlled state preparation (control_key = 0). This should *not* create the state in "register."
        circ = tree.preparation_circuit(register, control_register, control_key=0)

        # Get the final state of the circuit
        state = self.final_state(circ)

        # Make sure it's the |0> state (i.e., nothing has happened)
        self.assertTrue( np.allclose(state[:len(vec)], zero))

        # Do anti-controlled state preparation (control_key="1"). This should create the state in "register."
        circ = tree.preparation_circuit(register, control_register, control_key=1)

        # Get the final state of the circuit
        state = self.final_state(circ)

        self.assertTrue(np.allclose(state[:len(vec)], vec / np.linalg.norm(vec, ord=2)))

    def test_prep_with_ctrl_string_keys(self):
        """Does the above test with string control keys."""
        # Input vector
        vec = np.ones(2, dtype=np.float64)

        # Zero state
        zero = np.array([1, 0], dtype=np.float64)

        # Make a tree from the vector
        tree = BinaryTree(vec)

        # Register to store the vector
        register = QuantumRegister(1)

        # Register to control on
        control_register = QuantumRegister(1)

        # Do controlled state preparation (control_key = 0). This should *not* create the state in "register."
        circ = tree.preparation_circuit(register, control_register, control_key="0")

        # Get the final state of the circuit
        state = self.final_state(circ)

        # Make sure it's the |0> state (i.e., nothing has happened)
        self.assertTrue(np.allclose(state[:len(vec)], zero))

        # Do anti-controlled state preparation (control_key="1"). This should create the state in "register."
        circ = tree.preparation_circuit(register, control_register, control_key="1")

        # Get the final state of the circuit
        state = self.final_state(circ)

        self.assertTrue(np.allclose(state[:len(vec)], vec / np.linalg.norm(vec, ord=2)))

    def test_prep_with_ctrl_twoq_control_all_keys(self):
        """Tests a one qubit state is created when the correct key is provided, else nothing happens in the circuit."""
        # Input vector
        vec = np.array([1, 1], dtype=np.float64)

        # Zero state
        zero = np.array([1, 0], dtype=np.float64)

        # Make a binary tree from the vector
        tree = BinaryTree(vec)

        # Register to store the vector
        register = QuantumRegister(1)

        # Register to control on. Use two qubits here ==> four possible control_keys.
        control_register = QuantumRegister(2)

        for control_key in range(4):
            # Build the circuit
            circ = tree.preparation_circuit(register, control_register, control_key)

            # Get the final state of the circuit
            state = self.final_state(circ)

            # Make sure the state is the input vector if the correct control key is given, otherwise the |0> state.
            if control_key == 3:
                self.assertTrue(np.allclose(state[:len(vec)], vec / np.linalg.norm(vec, ord=2)))
            else:
                self.assertTrue(np.allclose(state[:len(vec)], zero))

    def test_prep_with_ctrl_twoq_control_all_keys_strings(self):
        """Tests a one qubit state is created when the correct key is provided, else nothing happens in the circuit.
        Provides control_keys as string arguments.
        """
        # Input vector
        vec = np.array([1, 1], dtype=np.float64)

        # Zero state
        zero = np.array([1, 0], dtype=np.float64)

        # Make a binary tree from the vector
        tree = BinaryTree(vec)

        # Register to store the vector
        register = QuantumRegister(1)

        # Register to control on. Use two qubits here ==> four possible control_keys.
        control_register = QuantumRegister(2)

        for control_key in ("00", "01", "10", "11"):
            # Build the circuit
            circ = tree.preparation_circuit(register, control_register, control_key)

            # Get the final state of the circuit
            state = self.final_state(circ)

            # Make sure the state is the input vector if the correct control key is given, otherwise the |0> state.
            if control_key == "11":
                self.assertTrue(np.allclose(state[:len(vec)], vec / np.linalg.norm(vec, ord=2)))
            else:
                self.assertTrue(np.allclose(state[:len(vec)], zero))

    def test_prep_with_ctrl_oneq_control_all_keys_negative_amplitudes(self):
        """Tests a one qubit state with negative amplitudes is created when the correct key is provided,
        else tests that nothing happens in the circuit.
        """
        # Input vector
        vec = np.array([-1, 1], dtype=np.float64)

        # Zero state
        zero = np.array([1, 0], dtype=np.float64)

        # Make a binary tree from the vector
        tree = BinaryTree(vec)

        # Register to store the vector
        register = QuantumRegister(1)

        # Register to control on. Use two qubits here ==> four possible control_keys.
        control_register = QuantumRegister(1)

        for control_key in range(2):
            # Build the circuit
            circ = tree.preparation_circuit(register, control_register, control_key)

            # Get the final state of the circuit
            state = self.final_state(circ)

            # Make sure the state is the input vector if the correct control key is given, otherwise the |0> state.
            if control_key == 1:
                self.assertTrue(np.allclose(state[:len(vec)], vec / np.linalg.norm(vec, ord=2)))
            else:
                self.assertTrue(np.allclose(state[:len(vec)], zero))

    def test_prep_with_ctrl_twoq_control_all_keys_negative_amplitudes(self):
        """Tests a one qubit state with negative amplitudes is created when the correct key is provided for a two qubit
        control circuit, else tests that nothing happens in the circuit.
        """
        # Input vector
        vec = np.array([1, -1], dtype=np.float64)

        # Zero state
        zero = np.array([1, 0], dtype=np.float64)

        # Make a binary tree from the vector
        tree = BinaryTree(vec)

        # Register to store the vector
        register = QuantumRegister(1)

        # Register to control on. Use two qubits here ==> four possible control_keys.
        control_register = QuantumRegister(2)

        for control_key in range(4):
            # Build the circuit
            circ = tree.preparation_circuit(register, control_register, control_key)

            # Get the final state of the circuit
            state = np.real(self.final_state(circ))

            # Make sure the state is the input vector if the correct control key is given, otherwise the |0> state.
            if control_key == 3:
                self.assertTrue(np.allclose(state[:len(vec)], vec / np.linalg.norm(vec, ord=2)))
            else:
                self.assertTrue(np.allclose(state[:len(vec)], zero))

    def test_prep_with_ctrl_three_qubit_state(self):
        """Tests creating a three qubit state with a control register of three qubits."""
        # Input vector
        vec = np.array([1, 1, 1, -5, 1, 1, 1, 1], dtype=np.float64)

        # Zero state
        zero = np.array([1, 0, 0, 0, 0, 0, 0, 0], dtype=np.float64)

        # Make a binary tree from the vector
        tree = BinaryTree(vec)

        # Register to store the vector
        register = QuantumRegister(3)

        # Register to control on.
        control_register = QuantumRegister(3)

        for control_key in range(8):
            # Build the circuit
            circ = tree.preparation_circuit(register, control_register, control_key)

            # Swap the qubits to compare with vector
            circ.swap(register[0], register[2])

            # Get the final state of the circuit
            state = np.real(self.final_state(circ))

            # Make sure the state is the input vector if the correct control key is given, otherwise the |0> state.
            if control_key == 7:
                self.assertTrue(np.allclose(state[:len(vec)], vec / np.linalg.norm(vec, ord=2)))
            else:
                self.assertTrue(np.allclose(state[:len(vec)], zero))

    def test_prep_with_ctrl_three_qubit_state_four_controls(self):
        """Tests creating a three qubit state with a control register of five qubits."""
        # Input vector
        vec = np.array([1, 1, 1, -5, 1, 1, 1, 1], dtype=np.float64)

        # Zero state
        zero = np.array([1, 0, 0, 0, 0, 0, 0, 0], dtype=np.float64)

        # Make a binary tree from the vector
        tree = BinaryTree(vec)

        # Register to store the vector
        register = QuantumRegister(3)

        # Register to control on.
        control_register = QuantumRegister(4)

        for control_key in range(16):
            # Build the circuit
            circ = tree.preparation_circuit(register, control_register, control_key)

            # Swap the qubits to compare with vector
            circ.swap(register[0], register[2])

            # Get the final state of the circuit
            state = np.real(self.final_state(circ))

            # Make sure the state is the input vector if the correct control key is given, otherwise the |0> state.
            if control_key == 15:
                self.assertTrue(np.allclose(state[:len(vec)], vec / np.linalg.norm(vec, ord=2)))
            else:
                self.assertTrue(np.allclose(state[:len(vec)], zero))

    # Note: This test takes a while (~5 minutes) to complete
    def test_prep_with_ctrl_three_qubit_state_five_controls(self):
        """Tests creating a three qubit state with a control register of five qubits."""
        # Input vector
        vec = np.array([1, 1, 1, -5, 1, 1, 1, 1], dtype=np.float64)

        # Zero state
        zero = np.array([1, 0, 0, 0, 0, 0, 0, 0], dtype=np.float64)

        # Make a binary tree from the vector
        tree = BinaryTree(vec)

        # Register to store the vector
        register = QuantumRegister(3)

        # Register to control on.
        control_register = QuantumRegister(5)

        for control_key in range(32):
            # Build the circuit
            circ = tree.preparation_circuit(register, control_register, control_key)

            # Swap the qubits to compare with vector
            circ.swap(register[0], register[2])

            # Get the final state of the circuit
            state = np.real(self.final_state(circ))

            # Make sure the state is the input vector if the correct control key is given, otherwise the |0> state.
            if control_key == 31:
                self.assertTrue(np.allclose(state[:len(vec)], vec / np.linalg.norm(vec, ord=2)))
            else:
                self.assertTrue(np.allclose(state[:len(vec)], zero))


if __name__ == "__main__":
    unittest.main()