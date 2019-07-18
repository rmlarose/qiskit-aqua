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

"""Module for Quantum Singular Value Estimation (QSVE).

QSVE is used as a subroutine in quantum recommendation systems [1],
where it was first introduced, and in linear systems solvers [2].

QSVE performs quantum phase estimation with the unitary W defined as

W =



References:

[1] Kerenedis and Prakash, Quantum Recommendation Systems.

[2] , , and Prakash, Quantum algorithm for dense linear systems of equations.


"""

# Imports
from itertools import permutations

from copy import deepcopy

import numpy as np

from qiskit.aqua.utils import CircuitFactory
from qiskit.aqua.circuits.gates.multi_control_toffoli_gate import mct
from qiskit.aqua.circuits.gates.multi_control_rotation_gates import _apply_mcu3_graycode as mcu3
from qiskit.aqua.circuits.gates.multi_control_rotation_gates import mcry
from qiskit import QuantumRegister, QuantumCircuit, execute, BasicAer


def mcz(circuit, controls, target, use_basis_gates):
    """Implements a multi-controlled X gate in a circuit. (Wrapper of mcu3 with correct angles.)"""
    mcu3(circuit, 0, 0, np.pi, controls, target, use_basis_gates)


class BinaryTree:
    """Binary tree data structure used to store and access matrix elements in QSVE."""
    def __init__(self, vector):
        """Initializes a BinaryTree.

        Args:
            vector : array-like
                Array of values in one row of a matrix.
        """
        # Make a copy of the vector
        vector = deepcopy(vector)

        # Store the number of values in the matrix row
        self._nvals = len(vector)

        # Make sure the matrix row has length that's a power of two
        # TODO: Give the option to pad the vector and do this automatically
        if self._nvals & (self._nvals - 1) != 0:
            raise ValueError(
                "Matrix row must have a number of elements that is a power of two. " +
                "Please append zero entries to the row."
            )

        # Store the input matrix_row
        self._values = list(vector)
        self._nvals = len(self._values)

        # ===========================================================
        # Construct the tree upside down (and then reverse the order)
        # ===========================================================

        # Store the sign information
        self._tree = [list(map(lambda x: np.sign(x), self._values))]

        # Store the magnitude squared values
        self._tree.append(list(map(lambda x: abs(x) ** 2, self._values)))

        # Sum adjacent elements to build the next row of the tree
        while len(self._tree[-1]) > 1:
            vals = []
            for ii in range(0, len(self._tree[-1]) - 1, 2):
                vals.append(self._tree[-1][ii] + self._tree[-1][ii + 1])
            self._tree.append(vals)

        # Reverse the order of the tree
        self._tree = list(reversed(self._tree))

    @property
    def data(self):
        """The data structure (list of lists) storing the binary tree.

        Return type: list<list>.
        """
        return self._tree

    @property
    def root(self):
        """Returns the root of the tree.

        Return type: float.
        """
        return self._tree[0][0]

    @property
    def number_leaves(self):
        """The number of leaves in the tree, equal to the length of the input vector.
        (Number of elements in last level of tree.)
        """
        return int(self._nvals)

    @property
    def number_levels(self):
        """The number of levels in the tree."""
        return int(np.ceil(np.log2(self._nvals)) + 1)

    def get_leaf(self, index):
        """Returns the indexed element.

        Args:
            index : int
                Index of leaf element to return.

        Return type: float.
        """
        return self._values[index]

    def get_level(self, level):
        """Returns a level in the tree.

        Examples:
            level = 0
                Returns the root of the tree.

            level = 1
                Returns a list of the two nodes below the root.

            etc.

        Return type: list
        """
        return self._tree[level]

    def get_element(self, level, index):
        """Returns an element in the tree.

        Args:
            level : int
                Level of the tree the element is in.

            index : int
                Index of the element in the level.

        Return type: float
        """
        return self._tree[level][index]

    def parent_index(self, level, index):
        """Returns the indices of the parent of a specified node.

        Args:
            level : int
                The node's level in the tree.

            index : int
                The node's index within a level.

        Return type: tuple<int, int>.
        """
        if level == 0 or level > self.number_levels:
            return None

        return level - 1, index // 2

    def parent_value(self, level, index):
        """Returns the value of the parent of a specified node.

                Args:
                    level : int
                        The node's level in the tree.

                    index : int
                        The node's index within a level.

                Return type: float.
                """
        # Check if root node
        if level == 0:
            return None

        # Get the level and index of the parent
        level, index = self.parent_index(level, index)

        # Return the parent value
        return self._tree[level][index]

    def left_child_index(self, level, index):
        """Returns the index of the left child of a specified parent node.

        Args:
            level : int
                The parent node's level in the tree.

            index : int
                The parent node's index within the level.

        Return type: tuple<int, int>.
        """
        if level == self.number_levels - 1:
            return None

        return level + 1, 2 * index

    def right_child_index(self, level, index):
        """Returns the index of the right child of a specified parent node.

            Args:
                level : int
                    The parent node's level in the tree.

                index : int
                    The parent node's index within the level.

            Return type: tuple<int, int>.
            """
        if level == self.number_levels - 1:
            return None

        return level + 1, 2 * index + 1

    def left_child_value(self, level, index):
        """Returns the value of the left child of a specified parent node.

            Args:
                level : int
                    The parent node's level in the tree.

                index : int
                    The parent node's index within the level.

            Return type: float.
            """
        if level == self.number_levels - 1:
            return None

        level, index = self.left_child_index(level, index)

        return self._tree[level][index]

    def right_child_value(self, level, index):
        """Returns the value of the right child of a specified parent node.

            Args:
                level : int
                    The parent node's level in the tree.

                index : int
                    The parent node's index within the level.

            Return type: float.
            """
        if level == self.number_levels - 1:
            return None

        level, index = self.right_child_index(level, index)

        return self._tree[level][index]

    def update_entry(self, index, value):
        """Updates an entry in the leaf and propagates changes up through the tree."""
        # TODO: Do this more efficiently.
        newvals = self._values
        newvals[index] = value
        self.__init__(newvals)

    def preparation_circuit(self, register, control_register=None, control_key=None):
        """Returns a circuit that encodes the leaf values (input values to the BinaryTree)in a quantum state.

        For example, if the vector [0.4, 0.4, 0.8, 0.2] is input to BinaryTree, then this method returns a circuit
        which prepares the state

        0.4|00> + 0.4|01> + 0.8|10> + 0.2|11>.

        This circuit consists of controlled-Y rotations, and has the following structure for two qubits:

                 |0> ----[Ry(theta1)]----@---------------O-----------
                                         |               |
                 |0> ---------------[Ry(theta2)]---[Ry(theta3)]------


        Here, the @ symbol represents a control and the O symbol represents an "anti-control" (controlled on |1> state).

        All gates can optionally be controlled on another control_register. See arguments below.

        Args:
            register : qiskit.QuantumRegister
                The state of this register will be the vector of the BinaryTree.

            control_register : qiskit.QuantumRegister
                Every gate added to the register will be controlled on all qubits in this register.

            control_key : Union[int, str]
                The control_key determines which qubits in the control_register are "anti-controls" or regular controls.

                For example, if the control_register has two qubits, the possible values for control_key are:

                        int     | str       | meaning
                        ==============================
                        0       | "00"      | Control on both qubits
                        1       | "01"      | Control on the first qubit, anti-control on the second qubit.
                        2       | "10"      | Anti-control on the first qubit, control on the second qubit.
                        3       | "11"      | Anti-control on both qubits.

                An example circuit for control_key = 1 is shown schematically below:

                        preparation_circuit(reg, ctrl_reg, 1) -->

                                    |  -------@-------
                        ctrl_reg    |         |
                                    |  -------O-------
                                              |
                                    |  ----|     |----
                        reg         |  ----|     |----
                                    |  ----|_____|----

                An example for control_key = 2 is shown schematically below:

                        preparation_circuit(reg, ctrl_reg, 2) -->

                                    |  -------O-------
                        ctrl_reg    |         |
                                    |  -------@-------
                                              |
                                    |  ----|     |----
                        reg         |  ----|     |----
                                    |  ----|_____|----

        """
        # =========================
        # Checks on input arguments
        # =========================

        # Make sure the register has enough qubits
        if int(2**len(register)) < self._nvals:
            raise ValueError(
                "Not enough qubits in input register to store vector. " +
                "A register with at least {} qubits is needed.".format(int(np.log2(self._nvals)))
            )

        # Make sure a control_key is provided if a control_register is provided
        if control_register is not None:
            if control_key is None:
                raise ValueError("If control_register is provided, a valid control_key must also be provided.")

        # Make sure a control_register is provided if the control_key is provided
        if control_key is not None:
            if control_register is None:
                raise ValueError("If control_key is provided, a valid control_register must also be provided.")

        if control_register:
            if type(control_register) != QuantumRegister:
                raise ValueError("Argument control_register must be of type qiskit.QuantumRegister.")

            # Get the number of qubits and dimension of the control register
            num_control_qubits = len(control_register)
            max_control_key = 2**num_control_qubits

        if control_key is not None:
            if not isinstance(control_key, (int, str)):
                raise ValueError("Argument control_key must be of type int or str.")

            # If provided as an integer
            if type(control_key) == int:
                if 0 > control_key > max_control_key:
                    raise ValueError("Invalid integer value for control_key. \
                                      This argument must be in the range [0, 2^(len(control_register)).")

                # Convert to a string
                control_key = np.binary_repr(control_key, num_control_qubits)

            # If provided as a string
            if type(control_key) == str:
                if len(control_key) != num_control_qubits:
                    raise ValueError(
                        "Invalid string value for control_key. " +
                        "The control_key must have the same number of characters as len(control_register)"
                    )

        # =======================
        # Get the quantum circuit
        # =======================

        # Get the base quantum circuit
        circ = QuantumCircuit(register)

        # Add the control register if provided
        # Note: the technique for adding controls for every gate will be adding the control_register_qubits to
        # a list of controlled qubits. If empty, nothing changes. If non-empty, we get the correct controls.
        if control_register:
            circ.add_register(control_register)
            control_register_qubits = control_register[:]
        else:
            control_register_qubits = []

        # Add ancilla qubits, if necessary, to do multi-controlled Y rotations
        if len(register) > 3:
            # TODO: Figure out exactly how many ancillae are needed.
            # TODO: Take into account the length of control_register_qubits above
            num_ancillae = max(len(register) - 3, 3)
            ancilla_register = QuantumRegister(num_ancillae)
            circ.add_register(ancilla_register)

        # ============================
        # Add the gates to the circuit
        # ============================

        # Do the initial pattern of X gates on control register (if provided) to get controls & anti-controls correct
        if control_register_qubits:
            for (ii, bit) in enumerate(control_key):
                if bit == "1":
                    circ.x(control_register[ii])

        # =========================================
        # Traverse the tree and add the Y-rotations
        # =========================================

        # Loop down the levels of the tree, starting at the first level (below the root)
        for level in range(0, self.number_levels - 1):
            # Within this level, loop from left to right across nodes
            for index in range(len(self._tree[level])):
                # Get the index of the node in binary
                bitstring = np.binary_repr(index, level)

                # Get the rotation angle
                parent = self._tree[level][index]
                left_child = self.left_child_value(level, index)

                # If the angle is zero, the gate is identity.
                if np.isclose(parent, 0.0):
                    continue
                else:
                    theta = 2 * np.arccos(np.sqrt(left_child / parent))

                mct_flag = False

                # If we're on the last row, shift the angle to take sign information into account
                if level == self.number_levels - 2:
                    # Get the actual (not squared) value of the left leaf child
                    left_child_leaf_index = 2 * index
                    left_child_leaf_value = self._values[left_child_leaf_index]

                    # Get the actual (not squared) value of the right leaf child
                    right_child_leaf_index = 2 * index + 1
                    right_child_leaf_value = self._values[right_child_leaf_index]

                    # Get the appropriate angle
                    if left_child_leaf_value < 0.0 and right_child_leaf_value > 0.0:
                        theta = 2 * np.arcsin(np.sqrt(left_child / parent)) + np.pi

                    elif left_child_leaf_value > 0.0 and right_child_leaf_value < 0.0:
                        theta = 2 * np.arcsin(np.sqrt(left_child / parent)) - np.pi

                    elif left_child_leaf_value < 0.0 and right_child_leaf_value < 0.0:
                        theta = 2 * np.arccos(np.sqrt(left_child / parent)) + np.pi

                        # Set flag to do the controlled bit flip on the target of the MCRY gate
                        mct_flag = True

                # =========================================
                # Do the Multi-Controlled-Y (MCRY) rotation
                # =========================================

                # Do X gates for anti-controls
                if level > 0:
                    for (ii, bit) in enumerate(bitstring):
                        if bit == "0":
                            if control_register_qubits:
                                mct(circ, control_register_qubits, register[ii], None, mode="noancilla")
                            else:
                                circ.x(register[ii])

                # Get all control qubits
                if level == 0:
                    all_control_qubits = control_register_qubits
                else:
                    all_control_qubits = control_register_qubits + register[:level]

                # For three qubits or less, no ancilla are needed to do the MCRY
                if len(register) <= 3:
                    if mct_flag:
                        if len(all_control_qubits) > 0:
                            mct(circ, all_control_qubits, register[level], None, mode="noancilla")
                        else:
                            circ.x(register[level])
                    if len(all_control_qubits) > 0:
                        mcry(circ, theta, all_control_qubits, register[level], None, mode="noancilla")
                    else:
                        circ.ry(theta, register[level])
                # For more than three qubits, ancilla are needed
                else:
                    if mct_flag:
                        if len(all_control_qubits) > 0:
                            mct(circ, all_control_qubits, register[level], ancilla_register)
                        else:
                            circ.x(register[level])
                    if len(all_control_qubits) > 0:
                        mcry(circ, theta, all_control_qubits, register[level], ancilla_register)
                    else:
                        circ.ry(theta, register[level])

                # Do X gates for anti-controls
                if level > 0:
                    for (ii, bit) in enumerate(bitstring):
                        if bit == "0":
                            if control_register_qubits:
                                mct(circ, control_register_qubits, register[ii], None, mode="noancilla")
                            else:
                                circ.x(register[ii])

        # Do the final pattern of X gates on the control qubits to get controls & anti-controls correct
        if control_register_qubits:
            for (ii, bit) in enumerate(control_key):
                if bit == "1":
                    circ.x(control_register[ii])

        return circ

    def __str__(self):
        """Returns a string representation of the tree."""
        # Get the shape of the array
        shape = (int(np.ceil(np.log2(self._nvals)) + 1), 2 * self._nvals - 1)

        # Initialize an empty array
        arr = np.empty(shape, dtype=object)

        # Returns the step (distance between elements) in the xth row of the array
        step = lambda x: 2**(x + 1)

        # Returns the skip (horizontal offset) in the xth row of the array
        skip = lambda x: 2**x - 1

        # Loop through the tree and store the values as formatted strings
        for ii in range(len(self._tree) - 1):
            for (jj, val) in enumerate(self._tree[ii]):
                # Format the value
                if np.isclose(val, 0.0):
                    string = "    "
                else:
                    string = "%0.2f" % val

                # Get the correct column index
                col = len(self._tree) - ii - 2
                col_index = skip(col) + step(col) * jj

                # Put the string in the array
                arr[ii][col_index] = string

        # Replace None objects with string separators.
        # Note: To format correctly, the number of spaces must be the same as
        # the number of chars in each value, which is by default 4.
        arr[arr == None] = "    "

        # Format the array as a string
        string = ""
        for row in arr:
            rowstring = ""
            for elt in row:
                rowstring += elt
            rowstring += "\n"
            string += rowstring
        return string


# ==========
# Unit tests
# ==========


def test_basic():
    """Basic checks for a BinaryTree."""
    # Instantiate a BinaryTree
    tree = BinaryTree([1, 1])

    # Simple checks
    assert np.isclose(tree.root, 2.0)
    assert tree.number_leaves == 2
    assert tree.number_levels == 2


def test_example_in_paper():
    """Tests correctness for the binary tree in the example given in
    Appendix A of the quantum recommendation systems paper.
    """
    # The same vector used in the paper
    row = [0.4, 0.4, 0.8, 0.2]

    # Construct the tree from the vector
    tree = BinaryTree(row)

    # Make sure the elements are equal
    assert np.isclose(tree.data[0][0], 1.0)
    assert np.isclose(tree.data[1][0], 0.32)
    assert np.isclose(tree.data[1][1], 0.68)
    assert np.isclose(tree.data[2][0], 0.16)
    assert np.isclose(tree.data[2][1], 0.16)
    assert np.isclose(tree.data[2][2], 0.64)
    assert np.isclose(tree.data[2][3], 0.04)


def test_print_small():
    """Tests the correct string format is obtained when printing a small tree."""
    tree = BinaryTree([1, 1])
    correct = "    2.00    \n1.00    1.00\n"
    assert tree.__str__() == correct


def test_print_medium():
    """Tests the correct string format is obtained when printing a tree with four leaves."""
    tree = BinaryTree([1, 1, 1, 1])
    correct = "        1.00        \n    0.50            0.50    \n0.25    0.25    0.25    0.25\n"
    assert tree.__str__() == correct


def test_number_leaves():
    """Tests the number of leaves is correct for a BinaryTree."""
    # Create a tree
    tree = BinaryTree(np.ones(128))

    # Make sure the number of leaves is correct
    assert tree.number_leaves == 128


def test_number_levels():
    """Tests the number of levels is correct for a BinaryTree."""
    # Create a tree
    tree = BinaryTree(np.ones(32))

    # Make sure the number of leaves is correct
    assert tree.number_levels == 6


def test_parent_indices():
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
    assert tree.parent_index(0, 0) is None

    # Test that the parent's of the first level are the root
    assert tree.parent_index(1, 0) == (0, 0)
    assert tree.parent_index(1, 1) == (0, 0)

    # Test that the parent's of the second level are correct
    assert tree.parent_index(2, 0) == (1, 0)
    assert tree.parent_index(2, 1) == (1, 0)
    assert tree.parent_index(2, 2) == (1, 1)
    assert tree.parent_index(2, 3) == (1, 1)


def test_parent_value():
    """Tests correctness for getting the parent value of a node."""
    # Get a BinaryTree
    tree = BinaryTree([1, 1, 1, 1])

    # Make sure the parent of the root is None
    assert tree.parent_value(0, 0) is None

    # Make sure the parent's of the first level (root) are correct
    assert np.isclose(tree.parent_value(1, 0), 4.0)
    assert np.isclose(tree.parent_value(1, 1), 4.0)

    # Make sure the parent's of the second level are correct
    assert np.isclose(tree.parent_value(2, 0), 2.0)
    assert np.isclose(tree.parent_value(2, 1), 2.0)
    assert np.isclose(tree.parent_value(2, 2), 2.0)
    assert np.isclose(tree.parent_value(2, 3), 2.0)


def test_left_child_index():
    """Tests getting the index of the left child."""
    # Get a BinaryTree
    tree = BinaryTree([1, 2, 3, 4])

    # Left child of the root
    assert tree.left_child_index(0, 0) == (1, 0)

    # Left child indices for the first level
    assert tree.left_child_index(1, 0) == (2, 0)
    assert tree.left_child_index(1, 1) == (2, 2)

    # Left child indices for leaves
    assert tree.left_child_index(2, 0) is None
    assert tree.left_child_index(2, 1) is None
    assert tree.left_child_index(2, 2) is None
    assert tree.left_child_index(2, 3) is None


def test_right_child_index():
    """Tests getting the index of a right child for a set of nodes."""
    # Get a BinaryTree
    tree = BinaryTree([1, 2, 3, 4])

    # Right child of the root
    assert tree.right_child_index(0, 0) == (1, 1)

    # Right child indices for the first level
    assert tree.right_child_index(1, 0) == (2, 1)
    assert tree.right_child_index(1, 1) == (2, 3)

    # Right child indices for leaves
    assert tree.right_child_index(2, 0) is None
    assert tree.right_child_index(2, 1) is None
    assert tree.right_child_index(2, 2) is None
    assert tree.right_child_index(2, 3) is None


def test_left_child_value():
    """Tests getting the value of a left child for a set of nodes."""
    # Get a BinaryTree
    tree = BinaryTree([1, 1, 1, 1])

    # Check the root value
    assert np.isclose(tree.root, 4.0)

    # Left child of the root
    assert np.isclose(tree.left_child_value(0, 0), 2.0)

    # Left child indices for the first level
    assert np.isclose(tree.left_child_value(1, 0), 1.0)
    assert np.isclose(tree.left_child_value(1, 1), 1.0)

    # Left child indices for leaves
    assert tree.left_child_value(2, 0) is None
    assert tree.left_child_value(2, 1) is None
    assert tree.left_child_value(2, 2) is None
    assert tree.left_child_value(2, 3) is None


def test_right_child_value():
    """Tests getting the value of a right child for a set of nodes."""
    # Get a BinaryTree
    tree = BinaryTree([1, 1, 1, 1])

    # Check root value
    assert np.isclose(tree.root, 4.0)

    # Right child of the root
    assert np.isclose(tree.right_child_value(0, 0), 2.0)

    # Right child indices for the first level
    assert np.isclose(tree.right_child_value(1, 0), 1.0)
    assert np.isclose(tree.right_child_value(1, 1), 1.0)

    # Right child indices for leaves
    assert tree.right_child_value(2, 0) is None
    assert tree.right_child_value(2, 1) is None
    assert tree.right_child_value(2, 2) is None
    assert tree.right_child_value(2, 3) is None


def final_state(circuit):
    """Returns the final state of the circuit as a numpy.ndarray."""
    # Get the unitary simulator backend
    sim = BasicAer.get_backend("unitary_simulator")

    # Execute the circuit
    job = execute(circuit, sim)

    # Get the final state
    unitary = np.array(job.result().results[0].data.unitary)
    return unitary[:, 0]


def test_prep_circuit_one_qubit():
    """Tests for correctness in preparation circuit on a single qubit."""
    # Two element vector
    vec = [1.0, 0.0]

    # Make a BinaryTree
    tree = BinaryTree(vec)

    # Get the state preparation circuit
    circ = tree.preparation_circuit(QuantumRegister(1))

    # Get the final state
    state = list(np.real(final_state(circ)))

    assert np.array_equal(state, vec)


def test_prep_circuit_one_qubit2():
    """Tests for correctness in preparation circuit on a single qubit."""
    # Two element vector
    vec = [0.0, 1.0]

    # Make a BinaryTree
    tree = BinaryTree(vec)

    # Get the state preparation circuit
    circ = tree.preparation_circuit(QuantumRegister(1))

    # Get the final state
    state = list(np.real(final_state(circ)))

    assert np.array_equal(state, vec)


def test_prep_circuit_one_qubit3():
    """Tests for correctness in preparation circuit on a single qubit."""
    # Two element vector
    vec = [0.6, 0.8]

    # Make a BinaryTree
    tree = BinaryTree(vec)

    # Get the state preparation circuit
    circ = tree.preparation_circuit(QuantumRegister(1))

    # Get the final state
    state = list(np.real(final_state(circ)))

    assert np.array_equal(state, vec)


def test_prep_circuit_example_in_paper():
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
    state = list(np.real(final_state(circuit)))
    assert np.allclose(state, vec)


def test_prep_circuit_three_qubits():
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
    state = list(np.real(final_state(circuit)))
    assert np.allclose(state, vec / np.linalg.norm(vec, ord=2))


def test_prep_circuit_medium():
    """Tests the state preparation circuit produces the correct state for a moderate number of qubits."""
    # Input vector
    vec = np.ones(16)

    # Make a tree from the vector
    tree = BinaryTree(vec)

    # Do the state preparation circuit
    circ = tree.preparation_circuit(QuantumRegister(4))

    # Check that the circuit produces the correct state
    # Note: No swaps are necessary here since all amplitudes are equal.
    state = np.real(final_state(circ))

    # Note: The output state has an additional ancilla needed to do the multi-controlled-Y rotations,
    # so we discard the additional (zero) amplitudes when comparing to the input vector
    assert np.allclose(state[:16], vec / np.linalg.norm(vec, ord=2))


def test_prep_circuit_large():
    """Tests the state preparation circuit produces the correct state for many qubits."""
    # Input vector
    vec = np.ones(64)

    # Make a tree from the vector
    tree = BinaryTree(vec)

    # Do the state preparation circuit
    circ = tree.preparation_circuit(QuantumRegister(6))

    # Check that the circuit produces the correct state
    # Note: No swaps are necessary here since all amplitudes are equal.
    state = np.real(final_state(circ))

    # Note: The output state has an additional ancilla needed to do the multi-controlled-Y rotations,
    # so we discard the additional (zero) amplitudes when comparing to the input vector
    assert np.allclose(state[:len(vec)], vec / np.linalg.norm(vec, ord=2))


def test_prep_circuit_large2():
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
    state = np.real(final_state(circ))

    # Note: The output state has an additional ancilla needed to do the multi-controlled-Y rotations,
    # so we discard the additional (zero) amplitudes when comparing to the input vector
    assert np.allclose(state[:len(vec)], vec / np.linalg.norm(vec, ord=2))


def test_prepare_negative_amplitudes():
    """Tests preparing a vector with negative amplitudes on a single qubit."""
    # Input vector
    vec = [0.6, -0.8]

    # Get a BinaryTree
    tree = BinaryTree(vec)

    # Get the state preparation circuit
    circuit = tree.preparation_circuit(QuantumRegister(1))

    # Make sure the final state of the circuit is the same as the input vector
    state = np.real(final_state(circuit))
    assert np.allclose(state, vec)


def test_prepare_negative_amplitudes2():
    """Tests preparing a vector with negative amplitudes on a single qubit."""
    # Input vector
    vec = [-0.6, 0.8]

    # Get a BinaryTree
    tree = BinaryTree(vec)

    # Get the state preparation circuit
    circuit = tree.preparation_circuit(QuantumRegister(1))

    # Make sure the final state of the circuit is the same as the input vector
    state = np.real(final_state(circuit))
    assert np.allclose(state, vec)


def test_prepare_negative_amplitudes3():
    """Tests preparing a vector with negative amplitudes on a single qubit."""
    # Input vector
    vec = [-0.6, -0.8]

    # Get a BinaryTree
    tree = BinaryTree(vec)

    # Get the state preparation circuit
    circuit = tree.preparation_circuit(QuantumRegister(1))

    # Make sure the final state of the circuit is the same as the input vector
    state = np.real(final_state(circuit))
    assert np.allclose(state, vec)


def test_prepare_negative_amplitudes_two_qubits():
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
    state = np.real(final_state(circuit))
    assert np.allclose(state, vec)


def test_prepare_negative_amplitudes_two_qubits2():
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
        state = np.real(final_state(circuit))
        assert np.allclose(state, vec / np.linalg.norm(vec, ord=2))


def test_prepare_negative_amplitudes_three_qubits():
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
    state = np.real(final_state(circuit))
    assert np.allclose(state, vec / np.linalg.norm(vec, ord=2))


def test_prepare_negative_amplitudes_four_qubits():
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
    state = np.real(final_state(circuit))

    # Only compare the first 16 amplitudes (ancillae are needed to do multi-controlled gates)
    assert np.allclose(state[:len(vec)], vec / np.linalg.norm(vec, ord=2))


def test_prep_circuit_negative_amplitudes_large():
    """Tests the state preparation circuit produces the correct state for many qubits."""
    # Input vector
    vec = -1.0 * np.ones(64)

    # Make a tree from the vector
    tree = BinaryTree(vec)

    # Do the state preparation circuit
    circ = tree.preparation_circuit(QuantumRegister(6))

    # Check that the circuit produces the correct state
    # Note: No swaps are necessary here since all amplitudes are equal.
    state = np.real(final_state(circ))

    # Note: The output state has an additional ancilla needed to do the multi-controlled-Y rotations,
    # so we discard the additional (zero) amplitudes when comparing to the input vector
    assert np.allclose(state[:len(vec)], vec / np.linalg.norm(vec, ord=2))


# ==========
# QSVE Class
# ==========

class QSVE(CircuitFactory):
    """Quantum Singular Value Estimation (QSVE) class."""

    def __init__(self, matrix, nprecision_bits=3):
        """Initializes a QSVE object.

        Args:
            matrix : numpy.ndarray
                The matrix to perform singular value estimation on.

            nprecision_bits : int
                The number of qubits to use in phase estimation.
                Equivalently, the number of bits of precision to read out singular values.
        """
        # Get the number of rows and columns in the matrix
        nrows, ncols = matrix.shape

        # Make sure the matrix is square
        # TODO: Pad matrix to automatically make it square
        if nrows != ncols:
            raise ValueError("Input matrix must be square.")

        # Make sure the number of columns is supported
        if ncols & (ncols - 1) != 0:
            raise ValueError("Number of columns in matrix must be a power of two.")

        # Store these as attributes
        self._matrix_nrows = nrows
        self._matrix_ncols = ncols

        # Store the number of qubits needed for the matrix rows and cols
        self._num_qubits_for_row = int(np.log2(ncols))
        self._num_qubits_for_col = int(np.log2(nrows))

        # Get the number of qubits needed for the circuit
        nqubits = int(np.log2(nrows * ncols) + nprecision_bits)

        # Initialize the base class
        CircuitFactory.__init__(self, nqubits)

        # Store a copy of the matrix
        self._matrix = deepcopy(matrix)

        # Get BinaryTree objects for each row of the matrix
        self._trees = []
        for row in matrix:
            self._trees.append(BinaryTree(row))

        # Flag to indicate whether the matrix has been shifted or not
        self._shifted = False

    @property
    def matrix(self):
        """The matrix to perform singular value estimation on."""
        return self._matrix

    @property
    def matrix_nrows(self):
        """The number of rows in the matrix."""
        return self._matrix_nrows

    @property
    def matrix_ncols(self):
        """The number of columns in the matrix."""
        return self._matrix_ncols

    def get_tree(self, index):
        """Returns the BinaryTree representing a matrix row."""
        return self._trees[index]

    def matrix_norm(self):
        """Returns the Froebenius norm of the matrix."""
        # Compute the value using the BinaryTree's storing matrix rows.
        # With this data structure, the Froebenius norm is the sum of all roots
        value = 0.0
        for tree in self._trees:
            value += tree.root
        return np.sqrt(value)

    def shift_matrix(self):
        """Shifts the matrix diagonal by the Froebenius norm to make all eigenvalues positive. That is,
        if A is the matrix of the system and ||A||_F is the Froebenius norm, this method does the shift

        A --> A + ||A||_F * I =: A'

        where I is the identity matrix of the same dimension as A.

        This transformation ensures all eigenvalues of A' are non-negative.

        Note: If the matrix has already been shifted (i.e., if this method has already been called), then
        calling this method again will do nothing.

        Modifies:
            The matrix of QSVE and the BinaryTrees.
        """
        # If the matrix is already shifted, do nothing
        if self._shifted:
            return

        # Compute the Froebenius norm
        norm = self.matrix_norm()

        # Shift each diagonal entry, updating both the tree and matrix
        for (diag, tree) in enumerate(self._trees):
            # Get the current value
            value = self._matrix[diag][diag]

            # Update the matrix
            self._matrix[diag][diag] = value + norm

            # Update the BinaryTree
            tree.update_entry(diag, value + norm)

        # Set the shifted flag to True
        self._shifted = True

    def build(self, circuit, qpe_register, row_register, col_register, pkb_register):
        """Adds the gates for one Controlled-W unitary.

        The input circuit must have at least four registers corresponding to the input arguments

        At a high-level, this circuit has the following structure:

                    QPE (p qubits)  -------@--------
                                           \
                    ROW (n qubits)  ----|      |----
                                        |      |
                    COL (m qubits)  ----|  W   |----
                                        |      |
                    PKB (1 qubit)   ----|______|----

        At a lower level, the controlled-W circuit is implemented as follows:

            QPE (p qubits)  ---------------------@------------------------------@-----------------
                                                 |                              |
            ROW (n qubits)  ----| V^dagger |-----O----| V |----|           |----|----|   |--------
                                                 |             | W^dagger  |    |    | W |
            COL (m qubits)  ---------------------|-------------|           |----O----|   |--------
                                                 |                              |
            PKB (1 qubit)   |-> -----------------X------------------------------X-----------------

        where @ is a control symbol and O is an "anti-control" symbol (i.e., controlled on the |0> state).

        TODO: Add "mathematical section" explaining what V and W are.

        Args:
            circuit : qiskit.QuantumCircuit
                The QuantumCircuit object that gates will be added to.
                This QuantumCircuit must have at least four registers, enumerated below.
                Any gates already in the circuit are un-modified. The gates to implement Controlled-W are added after
                these gates.

            qpe_register : qiskit.QuantumRegister
                Quantum register used for precision in phase estimation. In the diagrams above, this is labeled QPE.
                The number of qubits in this register (p) is chosen by the user.

            row_register : qiskit.QuantumRegister
                Quantum register used to load/store rows of the matrix. In the diagrams above, this is labeled ROW.
                The number of qubits in this register (m) must be m = log2(number of matrix rows).

            col_register : qiskit.QuantumRegister
                Quantum register used to load/store columns of the matrix. In the diagrams above, this is labeled COL.
                The number of qubits in this register (n) must be n = log2(number of matrix cols).

            pkb_register : Union[qiskit.QuantumRegister, qiskit.QuantumRegister.Qubit]
                Quantum register or qubit used for phase kickback (PKB). In the diagrams above, this is labeled PKB.
                If pbk_register is a register, it must have one qubit. Otherwise, it must be a single qubit.

        Returns:
            None

        Modifies:
            The input circuit.
            Adds gates to this circuit to implement the controlled-W unitary.
        """
        # =====================
        # Check input arguments
        # =====================

        if type(circuit) != QuantumCircuit:
            raise ValueError(
                "The argument circuit must be of type qiskit.QuantumCircuit."
            )

        if len(circuit.qregs) < 4:
            raise ValueError(
                "The input circuit does not have enough quantum registers."
            )

        if len(row_register) != len(col_register):
            raise ValueError(
                "Only square matrices are currently supported. \
                This means the row_register and col_register must have the same number of qubits."
            )

        if len(row_register) != self._num_qubits_for_row:
            raise ValueError(
                "Invalid number of qubits for row_register. This number should be {}".format(self._num_qubits_for_row)
            )

        if type(pkb_register) == QuantumRegister:
            pkb = pkb_register[0]
        elif type(pkb_register) == circuit.quantumregister.Qubit:
            pkb = pkb_register
        else:
            raise ValueError(
                "The argument pbk_register must be of type qiskit.QuantumRegister \
                or qiskit.circuit.quantumregister.Qubit"
            )


# ===================
# Unit tests for QSVE
# ===================


def test_create_qsve():
    """Basic test for instantiating a QSVE object."""
    # Matrix to perform QSVE on
    matrix = np.array([[1, 0], [0, 1]], dtype=np.float64)

    # Create a QSVE object
    qsve = QSVE(matrix)

    # Basic checks
    assert np.allclose(qsve.matrix, matrix)
    assert qsve.matrix_ncols == 2
    assert qsve.matrix_nrows == 2


def test_qsve_norm():
    """Tests correctness for computing the norm."""
    # Matrix to perform QSVE on
    matrix = np.array([[1, 0], [0, 1]], dtype=np.float64)

    # Create a QSVE object
    qsve = QSVE(matrix)

    # Make sure the Froebenius norm is correct
    assert np.isclose(qsve.matrix_norm(), np.sqrt(2))


def test_norm_random():
    """Tests correctness for computing the norm on random matrices."""
    for _ in range(100):
        # Matrix to perform QSVE on
        matrix = np.random.rand(4, 4)
        matrix += matrix.conj().T

        # Create a QSVE object
        qsve = QSVE(matrix)

        # Make sure the Froebenius norm is correct
        correct = np.linalg.norm(matrix)
        assert np.isclose(qsve.matrix_norm(), correct)


def test_shift_identity():
    """Tests shifting the identity matrix in QSVE."""
    # Matrix for QSVE
    matrix = np.identity(2)

    # Get a QSVE object
    qsve = QSVE(matrix)

    # Shift the matrix
    qsve.shift_matrix()

    # Get the correct shifted matrix
    correct = matrix + np.linalg.norm(matrix) * np.identity(2)

    # Make sure the QSVE shifted matrix is correct
    assert np.allclose(qsve.matrix, correct)


def test_shift():
    """Tests shifting an input matrix to QSVE."""
    # Matrix for QSVE
    matrix = np.array([[1, 2], [2, 4]], dtype=np.float64)

    # Compute the correct norm for testing the shift
    norm_correct = np.linalg.norm(matrix)

    # Get a QSVE object
    qsve = QSVE(matrix)

    # Get the BinaryTree's (one for each row of the matrix)
    tree1 = deepcopy(qsve.get_tree(0))
    tree2 = deepcopy(qsve.get_tree(1))

    # Shift the matrix
    qsve.shift_matrix()

    # Get the correct shifted matrix
    correct = matrix + norm_correct * np.identity(2)

    # Make sure the QSVE shifted matrix is correct
    assert np.allclose(qsve.matrix, correct)

    # Get the new BinaryTrees after shifting
    new_tree1 = qsve.get_tree(0)
    new_tree2 = qsve.get_tree(1)

    # Get the new correct tree values
    correct_new_tree1_values = np.array([tree1._values[0] + norm_correct, tree1._values[1]])
    correct_new_tree2_values = np.array([tree2._values[0], tree2._values[1] + norm_correct])

    # Make sure the BinaryTrees in the qsve object were updated correctly
    assert(np.array_equal(new_tree1._values, correct_new_tree1_values))
    assert(np.array_equal(new_tree2._values, correct_new_tree2_values))


# ==========================================================
# Unit tests for BinaryTree.preparation_circuit with control
# ==========================================================

def test_prep_circuit_with_control():
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
    state = final_state(circ)

    # Make sure it's the |0> state (i.e., nothing has happened)
    assert np.allclose(state[:len(vec)], zero)

    # Do anti-controlled state preparation (control_key="1"). This should create the state in "register."
    circ = tree.preparation_circuit(register, control_register, control_key=1)

    # Get the final state of the circuit
    state = final_state(circ)

    assert np.allclose(state[:len(vec)], vec / np.linalg.norm(vec, ord=2))


def test_prep_with_ctrl_string_keys():
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
    state = final_state(circ)

    # Make sure it's the |0> state (i.e., nothing has happened)
    assert np.allclose(state[:len(vec)], zero)

    # Do anti-controlled state preparation (control_key="1"). This should create the state in "register."
    circ = tree.preparation_circuit(register, control_register, control_key="1")

    # Get the final state of the circuit
    state = final_state(circ)

    assert np.allclose(state[:len(vec)], vec / np.linalg.norm(vec, ord=2))


def test_prep_with_ctrl_twoq_control_all_keys():
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
        state = final_state(circ)

        # Make sure the state is the input vector if the correct control key is given, otherwise the |0> state.
        if control_key == 3:
            assert np.allclose(state[:len(vec)], vec / np.linalg.norm(vec, ord=2))
        else:
            assert np.allclose(state[:len(vec)], zero)


def test_prep_with_ctrl_twoq_control_all_keys_strings():
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
        state = final_state(circ)

        # Make sure the state is the input vector if the correct control key is given, otherwise the |0> state.
        if control_key == "11":
            assert np.allclose(state[:len(vec)], vec / np.linalg.norm(vec, ord=2))
        else:
            assert np.allclose(state[:len(vec)], zero)


def test_prep_with_ctrl_oneq_control_all_keys_negative_amplitudes():
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
        state = final_state(circ)

        # Make sure the state is the input vector if the correct control key is given, otherwise the |0> state.
        if control_key == 1:
            assert np.allclose(state[:len(vec)], vec / np.linalg.norm(vec, ord=2))
        else:
            assert np.allclose(state[:len(vec)], zero)


def test_prep_with_ctrl_twoq_control_all_keys_negative_amplitudes():
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
        state = np.real(final_state(circ))

        # Make sure the state is the input vector if the correct control key is given, otherwise the |0> state.
        if control_key == 3:
            assert np.allclose(state[:len(vec)], vec / np.linalg.norm(vec, ord=2))
        else:
            assert np.allclose(state[:len(vec)], zero)


def test_prep_with_ctrl_three_qubit_state():
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
        state = np.real(final_state(circ))

        # Make sure the state is the input vector if the correct control key is given, otherwise the |0> state.
        if control_key == 7:
            assert np.allclose(state[:len(vec)], vec / np.linalg.norm(vec, ord=2))
        else:
            assert np.allclose(state[:len(vec)], zero)


if __name__ == "__main__":
    # Flags for testing
    TEST_QSVE = False
    TEST_BINARY_TREE = False
    TEST_TREE_CTRL = True

    # Unit tests for QSVE
    if TEST_QSVE:
        print("Now testing QSVE class...")
        test_create_qsve()
        test_qsve_norm()
        test_norm_random()
        test_shift_identity()
        test_shift()
        print("...All tests for QSVE passed!")

    # Unit tests for BinaryTree
    if TEST_BINARY_TREE:
        print("Now testing BinaryTree class...")
        test_basic()
        test_example_in_paper()
        test_print_small()
        # test_print_medium()
        test_number_leaves()
        test_number_levels()
        test_parent_indices()
        test_parent_value()
        test_left_child_index()
        test_right_child_index()
        test_left_child_value()
        test_right_child_value()
        test_prep_circuit_one_qubit()
        test_prep_circuit_one_qubit2()
        test_prep_circuit_one_qubit3()
        test_prep_circuit_example_in_paper()
        test_prep_circuit_three_qubits()
        test_prep_circuit_medium()
        test_prep_circuit_large()
        test_prep_circuit_large2()
        test_prepare_negative_amplitudes()
        test_prepare_negative_amplitudes2()
        test_prepare_negative_amplitudes3()
        test_prepare_negative_amplitudes_two_qubits()
        test_prepare_negative_amplitudes_two_qubits2()
        test_prepare_negative_amplitudes_three_qubits()
        test_prepare_negative_amplitudes_four_qubits()
        test_prep_circuit_negative_amplitudes_large()
        print("...All tests for BinaryTree passed!")

    if TEST_TREE_CTRL:
        print("Now testing BinaryTree.state_preparation with control...")
        test_prep_circuit_with_control()
        test_prep_with_ctrl_string_keys()
        test_prep_with_ctrl_twoq_control_all_keys()
        test_prep_with_ctrl_twoq_control_all_keys_strings()
        test_prep_with_ctrl_oneq_control_all_keys_negative_amplitudes()
        test_prep_with_ctrl_twoq_control_all_keys_negative_amplitudes()
        test_prep_with_ctrl_three_qubit_state()
        print("...All tests for BinaryTree.state_preparation with control passed!")